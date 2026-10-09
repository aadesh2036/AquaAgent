"""Module 08 steps 1-2: orchestrator skeleton against a real in-process sim app."""

from __future__ import annotations

import warnings

import pytest
from starlette.testclient import TestClient

from api.app.main import create_app
from api.app.settings import Settings
from api.clients.sim_client import SimClient
from shared import units
from shared.contracts.models import CONTRACT_VERSION, NetworkTopology, NetworkView
from sim.server.app import create_app as create_sim_app

warnings.filterwarnings("ignore", category=DeprecationWarning)


def _make(settings: Settings | None = None):
    sim_http = TestClient(create_sim_app(), base_url="http://sim")
    sc = SimClient("http://sim", client=sim_http)
    app = create_app(settings or Settings(mode="local"), sc)
    return TestClient(app), sc


@pytest.fixture()
def env():
    c, sc = _make()
    return c, sc


def view(r) -> NetworkView:
    assert r.status_code == 200, r.text
    assert r.headers["X-Aqua-Contract"] == CONTRACT_VERSION
    return NetworkView.model_validate(r.json())


def test_health_and_header(env):
    c, _ = env
    r = c.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "sim": "ok", "predictor": "degraded", "agent": "template"}
    assert r.headers["X-Aqua-Contract"] == CONTRACT_VERSION
    assert c.get("/api/nope").headers["X-Aqua-Contract"] == CONTRACT_VERSION


def test_reset_and_step(env):
    c, sc = env
    v = view(c.post("/api/session/reset", json={}))
    assert v.sim_time_s == 0 and len(v.nodes) == 8 and len(v.links) == 9
    assert v.nodes["2"].sensor_id == "S1" and v.nodes["1"].is_sensor is False
    v = view(c.post("/api/sim/step", json={"steps": 5}))
    assert v.sim_time_s == 1500 and v.clock == "00:25" and v.speed == 5
    snap = sc.snapshot(v.session_id)
    for nid, n in v.nodes.items():
        assert n.demand_lps == pytest.approx(units.m3s_to_lps(snap.nodes[nid].demand_m3s))
    assert 0 <= v.tank.level_pct <= 100
    assert v.pump.status == "ON"


def test_step_bounds(env):
    c, _ = env
    assert c.post("/api/sim/step", json={"steps": 21}).status_code == 422
    assert c.post("/api/sim/step", json={"steps": 0}).status_code == 422


def test_tap_raises_demand(env):
    c, _ = env
    view(c.post("/api/session/reset", json={}))
    before = view(c.post("/api/sim/step", json={"steps": 1}))
    v = view(c.post("/api/tap", json={"tap_id": "T2", "open": True}))
    assert v.taps["T2"].open is True
    assert any("Tap T2 opened" in e.text for e in v.events)
    after = view(c.post("/api/sim/step", json={"steps": 1}))
    assert after.nodes["4"].demand_lps - before.nodes["4"].demand_lps > 4
    assert after.taps["T2"].demand_lps > 4


def test_unknown_ids_422(env):
    c, _ = env
    assert c.post("/api/tap", json={"tap_id": "T9", "open": True}).status_code == 422
    assert c.post("/api/pipe/fault", json={"link_id": "99", "kind": "LEAK"}).status_code == 422
    assert c.post("/api/pipe/fault", json={"link_id": "9", "kind": "LEAK"}).status_code == 422
    assert c.post("/api/valve", json={"valve_id": "V9", "open": False}).status_code == 422


def test_leak_visual_and_pressure_and_reset():
    c1, _ = _make()
    c2, _ = _make()
    view(c1.post("/api/session/reset", json={"seed": 0}))
    view(c2.post("/api/session/reset", json={"seed": 0}))
    v = view(c1.post("/api/pipe/fault", json={"link_id": "4", "kind": "LEAK"}))
    assert v.links["4"].visual_fault == "LEAK"
    assert any(e.text == "Leak on pipe 4" for e in v.events)
    a = view(c1.post("/api/sim/step", json={"steps": 12}))
    b = view(c2.post("/api/sim/step", json={"steps": 12}))
    assert a.nodes["4"].pressure_m < b.nodes["4"].pressure_m
    v = view(c1.post("/api/pipe/fault", json={"link_id": "4", "kind": "RESET"}))
    assert v.links["4"].visual_fault == "NONE"
    assert v.events[-1].text == "Pipe 4 reset"
    v = view(c1.post("/api/pipe/fault", json={"link_id": "2", "kind": "BURST"}))
    assert v.links["2"].visual_fault == "BURST"


def test_valve_closed(env):
    c, _ = env
    view(c.post("/api/session/reset", json={}))
    v = view(c.post("/api/valve", json={"valve_id": "V1", "open": False}))
    assert v.valves["V1"].open is False and v.events[-1].text == "Valve V1 closed"
    v = view(c.post("/api/sim/step", json={"steps": 1}))
    assert v.links["7"].flow_lps < 1e-3 and v.links["7"].status == "CLOSED"


def test_pipe_close_only_status(env):
    c, _ = env
    view(c.post("/api/session/reset", json={}))
    view(c.post("/api/pipe/fault", json={"link_id": "5", "kind": "CLOSE"}))
    v = view(c.post("/api/sim/step", json={"steps": 1}))
    assert v.links["5"].visual_fault == "NONE" and v.links["5"].status == "CLOSED"


def test_topology(env):
    c, _ = env
    r = c.get("/api/network/topology")
    t = NetworkTopology.model_validate(r.json())
    assert t.sensor_layout and [s.sensor_id for s in t.sensor_layout.pressure] == ["S1", "S2", "S3"]
    assert "hydraulics" not in r.json() and "inp_path" not in r.json()


def test_no_leak_of_hidden(env):
    c, _ = env
    out = [
        c.post("/api/session/reset", json={}).text,
        c.get("/api/network/topology").text,
        c.post("/api/pipe/fault", json={"link_id": "4", "kind": "BURST"}).text,
        c.post("/api/sim/step", json={"steps": 3}).text,
        c.get("/api/network/state").text,
    ]
    for t in out:
        assert "LK_" not in t and "hidden" not in t


def test_not_implemented_routes(env):
    c, _ = env
    for r in (
        c.post("/api/challenge/start", json={}),
        c.get("/api/challenge/status"),
        c.post("/api/agent/diagnose", json={}),
    ):
        assert r.status_code == 501
        assert r.json() == {"detail": "NOT IMPLEMENTED — module 08 step 5 / module 07"}


def test_aws_key():
    c, _ = _make(Settings(mode="aws", api_key="secret"))
    assert c.get("/api/network/topology").status_code == 401
    assert c.get("/api/network/topology").headers["X-Aqua-Contract"] == CONTRACT_VERSION
    assert c.get("/api/network/topology", headers={"X-Api-Key": "bad"}).status_code == 401
    assert c.get("/api/network/topology", headers={"X-Api-Key": "secret"}).status_code == 200
    assert c.get("/api/health").status_code == 200  # ALB health check sends no key (§3.2)
    r = c.options(
        "/api/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert r.status_code != 401 and r.headers["X-Aqua-Contract"] == CONTRACT_VERSION


def test_sim_down():
    sc = SimClient("http://127.0.0.1:9", timeout=0.5)
    c = TestClient(create_app(Settings(mode="local"), sc))
    assert c.get("/api/health").json()["sim"] == "down"
    r = c.get("/api/network/state")
    assert r.status_code == 503
    assert r.json() == {"detail": "Simulation engine unreachable at http://127.0.0.1:9"}
    assert r.headers["X-Aqua-Contract"] == CONTRACT_VERSION


@pytest.mark.parametrize("call", ["state", "step", "tap"])
def test_stale_sim_session_recovers(call):
    sim_app = create_sim_app()
    sc = SimClient("http://sim", client=TestClient(sim_app, base_url="http://sim"))
    c = TestClient(create_app(Settings(mode="local"), sc))
    view(c.post("/api/session/reset", json={"seed": 3}))
    view(c.post("/api/sim/step", json={"steps": 5}))
    # simulate sim restart: swap in a fresh sim app behind the same client
    sc._client = TestClient(create_sim_app(), base_url="http://sim")
    if call == "state":
        v = view(c.get("/api/network/state"))
        assert v.sim_time_s == 0
    elif call == "step":
        v = view(c.post("/api/sim/step", json={"steps": 1}))
        assert v.sim_time_s == 300 and v.speed == 1
    else:
        v = view(c.post("/api/tap", json={"tap_id": "T1", "open": True}))
        assert v.taps["T1"].open
    assert v.events[0].text == "Simulation restarted — session reset"
    assert v.links["4"].visual_fault == "NONE"


def test_aws_mode_health_is_open_but_routes_need_key():
    c, _ = _make(Settings(mode="aws", api_key="k"))
    assert c.get("/api/health").status_code == 200  # ALB health check sends no key
    assert c.get("/api/network/state").status_code == 401
    assert c.get("/api/network/state", headers={"X-Api-Key": "k"}).status_code == 200
