"""Predictor service: §7.9 over HTTP, firewall rejection, SageMaker-compatible routes (BI-26)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from ml.tests.test_predict_parity import _window
from shared.contracts.models import PredictorResponse

TGZ = sorted(Path("data/models/predictor").glob("mlp_ds1_*/model.tar.gz"))
pytestmark = pytest.mark.skipif(not TGZ, reason="needs a packaged artifact (python -m ml.predictor.package)")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from ml.serve.app import create_app

    return TestClient(create_app(str(TGZ[-1])))


@pytest.fixture(scope="module")
def body(client):
    from ml.predictor.predict import load_artifact

    art = load_artifact(str(TGZ[-1]))
    with np.load("data/features/ds1/val.npz") as z:
        val = {k: z[k] for k in z.files}
    window = _window(val, art, range(40, 52))
    return {
        "model_version": art.meta["model_version"],
        "mode": "leave_one_out",
        "sensor_window": window.model_dump(),
    }


def test_health(client) -> None:
    r = client.get("/predictor/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.headers["X-Aqua-Contract"].startswith("backbone/")


@pytest.mark.parametrize("path", ["/predictor/predict", "/invocations"])
def test_predict_returns_contract(client, body, path) -> None:
    r = client.post(path, json=body)
    assert r.status_code == 200, r.text
    resp = PredictorResponse.model_validate(r.json())
    assert resp.reconstruct and set(resp.leave_one_out) == {"S1", "S2", "S3"}
    assert set(resp.leave_one_out_flow) == {"F1", "F2"}


def test_wrong_model_version_is_409(client, body) -> None:
    assert client.post("/predictor/predict", json={**body, "model_version": "other"}).status_code == 409


def test_ground_truth_fields_are_rejected(client, body) -> None:
    leaky = {**body, "sensor_window": {**body["sensor_window"], "hidden": {"leak_nodes": {"LK_4": 0.003}}}}
    assert client.post("/predictor/predict", json=leaky).status_code == 422
    snap = {**body, "sensor_window": {"nodes": {"4": {"pressure_m": 40.0, "leak_m3s": 0.01}}}}
    assert client.post("/predictor/predict", json=snap).status_code == 422


def test_ping(client) -> None:
    assert client.get("/ping").status_code == 200
