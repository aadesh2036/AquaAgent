"""Offline == online features, and predict() honours the §7.9 contract (module 04 steps 2 and 5)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch

from ml.features.tensorize import tensorize
from ml.predictor.masking import default_masks
from shared.contracts.models import PredictorResponse, SensorWindow

MODELS = sorted(Path("data/models/predictor").glob("*_ds1_*/meta.json"))
pytestmark = pytest.mark.skipif(
    not MODELS or not Path("data/features/ds1/val.npz").exists(), reason="needs features + a trained artifact"
)
KEYS = ("p_obs", "p_obs_lag1", "p_obs_lag3", "q_obs", "ctx")


@pytest.fixture(scope="module")
def artifact():
    from ml.predictor.predict import load_artifact

    return load_artifact(str(MODELS[-1].parent))


@pytest.fixture(scope="module")
def val():
    with np.load("data/features/ds1/val.npz") as z:
        return {k: z[k] for k in z.files}


def _window(val, art, rows) -> SensorWindow:
    gs, graph = art.gs, art.graph
    steps = []
    for r in rows:
        steps.append(
            {
                "sim_time_s": int(val["sim_time_s"][r]),
                "pressure_m": {
                    s: float(val["p_obs"][r, gs.node_order.index(n)])
                    for s, n in graph["pressure_sensors"].items()
                },
                "flow_lps": {
                    f: float(val["q_obs"][r, i]) for i, f in enumerate(sorted(graph["flow_sensors"]))
                },
                "context": {
                    "time_of_day_s": int(val["ctx"][r, 0]),
                    "tank_level_m": float(val["ctx"][r, 1]),
                    "pump_status": int(val["ctx"][r, 2]),
                    "pump_flow_lps": float(val["ctx"][r, 3]),
                    "reservoir_head_m": float(val["ctx"][r, 4]),
                },
            }
        )
    return SensorWindow(
        network_id=graph["network_id"], sensor_layout_id=graph["sensor_layout_id"], window=steps
    )


@pytest.mark.parametrize("end", [0, 2, 150, 288])
@pytest.mark.parametrize("drop", [None, "S2", "F1"])
def test_offline_equals_online_features(artifact, val, end, drop) -> None:
    from ml.predictor.predict import window_to_features

    rows = list(range(max(0, end - 11), end + 1))  # first sim of the split, steps ≤ end
    x_on, e_on = window_to_features(_window(val, artifact, rows), artifact, mask_sensor=drop)
    b = {k: torch.from_numpy(val[k][[end]]) for k in KEYS}
    pm, qm = default_masks(1, artifact.gs, drop=drop)
    x_off, e_off = tensorize(b, pm, qm, artifact.gs)
    assert torch.allclose(x_on, x_off, atol=1e-6) and torch.allclose(e_on, e_off, atol=1e-6)


def test_predict_contract(artifact, val) -> None:
    from ml.predictor.predict import predict

    resp = predict(_window(val, artifact, range(100, 112)), artifact, artifact.meta["model_version"])
    PredictorResponse.model_validate(resp.model_dump())
    assert set(resp.leave_one_out) == {"S1", "S2", "S3"}
    assert set(resp.leave_one_out_flow) == {"F1", "F2"}
    assert set(resp.reconstruct.pressure_m) == {"2", "3", "4", "5", "6", "7", "8"}
    truth = val["p_true"][111]
    for node in ("3", "5", "7"):  # hidden junctions within 1 m on a normal step
        assert abs(resp.reconstruct.pressure_m[node] - truth[artifact.gs.node_order.index(node)]) < 1.0


def test_predict_rejects_non_sensor_window(artifact) -> None:
    from ml.predictor.predict import predict

    with pytest.raises(TypeError):
        predict({"nodes": {}, "hidden": {"leak_nodes": {}}}, artifact, "x")  # type: ignore[arg-type]
