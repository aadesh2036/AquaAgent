"""LOO residuals and z-scores (BACKBONE §9.2, §7.10).

Online (api, per step):   ``residual_frame(window, predict(window, …), sigmas)``.
Offline (tuning/eval):    ``loo_residuals(arrays, artifact)`` — the same 5 leave-one-out predictions as
``predict()`` (same ``tensorize`` path, default layout with one sensor hidden), batched over all rows.
Equality of the two paths is tested in ``ml/tests/test_anomaly_residuals.py``.

r_s = observed_s − LOO_prediction_s (pressure m for S1–S3, flow L/s for F1–F2); z_s = r_s / σ_s,
σ_s = std of r_s on validation NORMAL rows (operational sims + pre-fault steps). σ is fixed (no EMA).
"""

from __future__ import annotations

import numpy as np
import torch

from ml.anomaly.frames import residual_frame  # noqa: F401  (re-export; torch-free home)
from ml.features.tensorize import tensorize
from ml.predictor.masking import default_masks
from shared.contracts.models import (
    FLOW_SENSORS,
    PRESSURE_SENSORS,
)

SENSORS: tuple[str, ...] = (*PRESSURE_SENSORS, *FLOW_SENSORS)  # S1, S2, S3, F1, F2 — column order everywhere


@torch.no_grad()
def loo_residuals(
    arrays: dict[str, np.ndarray], artifact, rows: np.ndarray | None = None, bs: int = 16384
) -> np.ndarray:
    """[R, 5] residuals (S1, S2, S3, F1, F2) for the given rows of a features split."""
    gs, model = artifact.gs, artifact.model
    rows = np.arange(len(arrays["sim_code"])) if rows is None else rows
    out = np.empty((len(rows), len(SENSORS)), np.float64)
    keys = ("p_obs", "p_obs_lag1", "p_obs_lag3", "q_obs", "ctx")
    for i in range(0, len(rows), bs):
        sl = rows[i : i + bs]
        b = {k: torch.from_numpy(np.ascontiguousarray(arrays[k][sl])) for k in keys}
        for c, sid in enumerate(SENSORS):
            pm, qm = default_masks(len(sl), gs, drop=sid)
            x, e = tensorize(b, pm, qm, gs)
            head_z, flow_z = model(x, e, gs)
            if sid.startswith("S"):
                j = gs.default_sensor_idx[int(sid[1:]) - 1]
                pred = gs.head_z_to_pressure(head_z)[:, j]
                obs = b["p_obs"][:, j]
            else:
                f = int(sid[1:]) - 1
                pred = gs.z_to_flow(flow_z)[:, f]
                obs = b["q_obs"][:, f]
            # same rounding as PredictorResponse (4 dp) so offline == online exactly
            out[i : i + len(sl), c] = np.round(obs.double().numpy(), 4) - np.round(pred.double().numpy(), 4)
    return out


def estimate_sigmas(val_normal_residuals: np.ndarray) -> dict[str, float]:
    """σ per sensor = std of val-normal residuals ([R, 5], SENSORS order)."""
    sd = np.asarray(val_normal_residuals, np.float64).std(axis=0)
    return {s: float(v) for s, v in zip(SENSORS, sd, strict=True)}


def estimate_binned_sigmas(residuals: np.ndarray, pump_flow_lps: np.ndarray, n_bins: int = 5) -> dict:
    """σ per sensor conditioned on demand level: quantile bins of SCADA pump flow (val-normal rows only).

    Residual spread grows ~2.5× at the highest demand (module 05 diagnosis, 2026-10-09); a fixed
    lookup on a known context value is still a *fixed* σ (no adaptation to the current residuals).
    """
    edges = np.quantile(pump_flow_lps, np.linspace(0, 1, n_bins + 1)[1:-1])
    b = np.digitize(pump_flow_lps, edges)
    table = [estimate_sigmas(residuals[b == k]) for k in range(n_bins)]
    return {"by": "pump_flow_lps", "edges": [float(e) for e in edges], "sigmas": table}


def sigmas_for(pump_flow_lps: float | None, binned: dict) -> dict[str, float]:
    """σ dict for the current step (``pump_flow_lps`` None → middle bin)."""
    if pump_flow_lps is None:
        return binned["sigmas"][len(binned["sigmas"]) // 2]
    return binned["sigmas"][int(np.digitize(pump_flow_lps, binned["edges"]))]


def sigma_matrix(pump_flow_lps: np.ndarray, binned: dict) -> np.ndarray:
    """[R, 5] σ per row (vectorised ``sigmas_for``)."""
    tab = np.array([[d[s] for s in SENSORS] for d in binned["sigmas"]])
    return tab[np.digitize(pump_flow_lps, binned["edges"])]
