"""Detector + localiser service (BI-27): health, per-session streaming, localiser, firewall."""

from __future__ import annotations

from pathlib import Path

import pytest

DET = Path("data/models/anomaly/thr_ds1_202610091624")
SIG = Path("data/models/localisation/sig_ds1_202610091648")
pytestmark = pytest.mark.skipif(not (DET.exists() and SIG.exists()), reason="needs detector + signatures")
CTX = {
    "time_of_day_s": 36000,
    "tank_level_m": 2.0,
    "pump_status": 1,
    "pump_flow_lps": 40.0,
    "reservoir_head_m": 213.36,
}


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from ml.serve.detector_app import create_app

    return TestClient(create_app(str(DET), str(SIG)))


def _frame(t: int, f2: float) -> dict:
    return {"sim_time_s": t, "residuals": {"S1": 0.0, "S2": 0.0, "S3": 0.0, "F1": 0.0, "F2": f2}, "z": {}}


def test_health(client) -> None:
    h = client.get("/detector/health").json()
    assert h["status"] == "ok" and h["signatures"] and set(h["sigmas"]) == {"S1", "S2", "S3", "F1", "F2"}
    assert client.get("/detector/health").headers["X-Aqua-Contract"].startswith("backbone/")


def test_sessions_are_independent_and_sustained_gap_alarms(client) -> None:
    for sid in ("a", "b"):
        client.post("/detector/reset", json={"session_id": sid})
    out_a = [
        client.post(
            "/detector/update", json={"session_id": "a", "frame": _frame(300 * i, 3.0), "context": CTX}
        ).json()["status"]
        for i in range(30)
    ]
    out_b = client.post(
        "/detector/update", json={"session_id": "b", "frame": _frame(0, 0.0), "context": CTX}
    ).json()["status"]
    assert "ANOMALY" in out_a and out_b == "NORMAL"


def test_localiser_ranks(client) -> None:
    r = client.post(
        "/localiser/rank", json={"z_mean": {"S1": -1, "S2": -2, "S3": -3, "F1": 1, "F2": -8}}
    ).json()
    assert len(r["candidates"]) == 3 and r["probable_zone"]["zone_id"]


def test_ground_truth_is_rejected(client) -> None:
    bad = {"session_id": "a", "frame": _frame(0, 0.0) | {"leak_m3s": 0.01}, "context": CTX}
    assert client.post("/detector/update", json=bad).status_code == 422
