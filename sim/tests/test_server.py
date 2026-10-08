"""Step 7 tests: FastAPI sim server (BACKBONE §7.14.2)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from shared.contracts.models import CONTRACT_VERSION, HydraulicSnapshot
from sim.server.app import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def new_session(c, **kw):
    body = {"network_id": "net_epa_tutorial_v1", "seed": 1, "timestep_s": 300} | kw
    r = c.post("/sim/session", json=body)
    return r


def sid(c):
    r = new_session(c)
    assert r.status_code == 200
    return r.json()["session_id"]


def event(t, ekind, target=None, **params):
    return {
        "event_id": f"e{t}{ekind}",
        "sim_time_s": t,
        "source": "user",
        "kind": ekind,
        "target_id": target,
        "params": params,
        "hidden": False,
    }


def test_health(client):
    r = client.get("/sim/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "wntr_version": "1.5.0"}
    assert r.headers["X-Aqua-Contract"] == CONTRACT_VERSION


def test_create_snapshot_event_advance(client):
    s = sid(client)
    snap = HydraulicSnapshot.model_validate(client.get(f"/sim/session/{s}/snapshot").json())
    assert snap.sim_time_s == 0 and snap.hidden is not None
    r = client.post(f"/sim/session/{s}/event", json=event(0, "TAP_SET", "T2", open=True))
    assert r.json() == {"applied": True}
    r = client.post(f"/sim/session/{s}/advance", json={"steps": 5})
    assert r.status_code == 200 and r.headers["X-Aqua-Contract"] == CONTRACT_VERSION
    snaps = [HydraulicSnapshot.model_validate(x) for x in r.json()]
    assert [x.sim_time_s for x in snaps] == [300, 600, 900, 1200, 1500]


def test_leak_vs_parallel_session(client):
    a, b = sid(client), sid(client)
    client.post(f"/sim/session/{a}/event", json=event(0, "PIPE_FAULT", "4", kind="LEAK"))
    la = client.post(f"/sim/session/{a}/advance", json={"steps": 12}).json()
    lb = client.post(f"/sim/session/{a}/advance", json={"steps": 12}).json()
    base = client.post(f"/sim/session/{b}/advance", json={"steps": 12}).json()
    base2 = client.post(f"/sim/session/{b}/advance", json={"steps": 12}).json()
    assert "LK_4" in lb[-1]["hidden"]["leak_nodes"] and la[-1]["sim_time_s"] == 3600
    assert lb[-1]["nodes"]["4"]["pressure_m"] < base2[-1]["nodes"]["4"]["pressure_m"] - 0.1
    assert base[-1]["hidden"]["leak_nodes"] == {}


def test_errors(client):
    s = sid(client)
    assert (
        client.post(f"/sim/session/{s}/event", json=event(300, "TAP_SET", "T1", open=True)).status_code == 422
    )
    assert (
        client.post(f"/sim/session/{s}/event", json=event(0, "TAP_SET", "T9", open=True)).status_code == 422
    )
    assert client.post(f"/sim/session/{s}/advance", json={"steps": 21}).status_code == 422
    assert client.post(f"/sim/session/{s}/advance", json={"steps": 0}).status_code == 422
    assert client.get("/sim/session/sim_nope/snapshot").status_code == 404
    assert client.post("/sim/session/sim_nope/advance", json={"steps": 1}).status_code == 404
    assert new_session(client, timestep_s=60).status_code == 422
    r = new_session(client, network_id="nope")
    assert r.status_code == 422 and "detail" in r.json()


def test_fork_and_reset(client):
    s = sid(client)
    client.post(f"/sim/session/{s}/advance", json={"steps": 4})
    before = client.get(f"/sim/session/{s}/snapshot").json()
    r = client.post(
        f"/sim/session/{s}/fork_what_if",
        json={"events": [event(1200, "PIPE_FAULT", "4", kind="BURST")], "horizon_steps": 6},
    )
    assert r.status_code == 200 and len(r.json()) == 6 and r.json()[0]["sim_time_s"] == 1500
    assert r.json()[-1]["hidden"]["leak_nodes"]
    assert client.get(f"/sim/session/{s}/snapshot").json() == before
    r = client.post(f"/sim/session/{s}/reset")
    assert r.status_code == 200 and r.json()["sim_time_s"] == 0


def test_lru_eviction():
    c = TestClient(create_app(max_sessions=2))
    a, b, d = sid(c), sid(c), sid(c)
    assert c.get(f"/sim/session/{a}/snapshot").status_code == 404
    assert c.get(f"/sim/session/{b}/snapshot").status_code == 200
    assert c.get(f"/sim/session/{d}/snapshot").status_code == 200


def test_no_boto3_under_sim():
    for path in Path(__file__).resolve().parents[1].rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            assert not any(n.split(".")[0] in {"boto3", "botocore"} for n in names), path
