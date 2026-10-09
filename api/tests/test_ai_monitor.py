"""AI monitor end-to-end through the API (BI-27): normal → quiet, burst → ANOMALY + BY AI highlight; firewall."""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from api.app.main import create_app
from api.app.settings import Settings
from api.clients.sim_client import SimClient
from sim.server.app import create_app as create_sim_app

warnings.filterwarnings("ignore", category=DeprecationWarning)
PRED = Path("data/models/predictor/gnn_ds1_202610090559/model.tar.gz")
DET = Path("data/models/anomaly/thr_ds1_202610091624")
SIG = Path("data/models/localisation/sig_ds1_202610091648")
pytestmark = pytest.mark.skipif(
    not (PRED.exists() and DET.exists() and SIG.exists()), reason="needs local model artifacts"
)


@pytest.fixture(scope="module")
def client():
    sim_http = TestClient(create_sim_app(), base_url="http://sim")
    s = Settings(mode="local", predictor_artifact=str(PRED), thresholds_uri=str(DET), signatures_uri=str(SIG))
    return TestClient(create_app(s, SimClient("http://sim", client=sim_http)))


def test_ai_listens_detects_and_highlights(client) -> None:
    assert client.get("/api/health").json()["predictor"] == "ok"
    client.post("/api/session/reset", json={"seed": 3})
    for _ in range(6):
        client.post("/api/sim/step", json={"steps": 20})
    ai = client.get("/api/ai/state").json()
    assert ai["enabled"] and ai["status"] == "NORMAL" and ai["steps_observed"] == 96  # history cap (8 h)
    assert set(ai["nodes"]) == {"2", "3", "4", "5", "6", "7", "8"} and set(ai["flows"]) == {"F1", "F2"}

    client.post("/api/pipe/fault", json={"link_id": "5", "kind": "BURST"})
    for _ in range(36):
        v = client.post("/api/sim/step", json={"steps": 1}).json()
        ai = client.get("/api/ai/state").json()
        if ai["status"] == "ANOMALY":
            break
    assert ai["status"] == "ANOMALY" and v["network_status"] == "ANOMALY"
    hl = ai["highlight"]
    assert hl["label"] == "BY AI" and hl["probable_zone"] and len(hl["candidates"]) == 3
    assert ai["notifications"] and ai["notifications"][-1]["status"] == "ANOMALY"

    body = json.dumps(ai)
    assert "LK_" not in body and "leak_m3s" not in body and "hidden" not in body  # §11 firewall

    # operator repairs the pipe → AI re-arms, alarm and highlight clear, recovery is logged
    client.post("/api/pipe/fault", json={"link_id": "5", "kind": "RESET"})
    after = client.get("/api/ai/state").json()
    assert after["status"] == "NORMAL" and after["highlight"] is None
    assert after["notifications"][-1]["status"] == "NORMAL"
    for _ in range(4):  # keeps listening (score history grows) after the repair
        client.post("/api/sim/step", json={"steps": 5})
    assert client.get("/api/ai/state").json()["status"] in ("NORMAL", "WATCH")
