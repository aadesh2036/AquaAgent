"""Metrics table of BACKBONE §9.5.

Implementation: docs/modules/05_ANOMALY_LOCALISATION.md
"""

from __future__ import annotations


def predictor_metrics(y_true, y_pred, mask) -> dict:
    """MAE / RMSE / R² / MAPE (pressure, m) over the entries where ``mask`` is true (module 04).

    R² is pooled over all masked entries (so it includes between-node variance); MAPE uses |true|.
    """
    import numpy as np

    t = np.asarray(y_true, np.float64)[np.asarray(mask, bool)]
    p = np.asarray(y_pred, np.float64)[np.asarray(mask, bool)]
    err = p - t
    sst = float(np.sum((t - t.mean()) ** 2)) if t.size else 0.0
    return {
        "mae_m": float(np.mean(np.abs(err))) if t.size else float("nan"),
        "rmse_m": float(np.sqrt(np.mean(err**2))) if t.size else float("nan"),
        "r2": 1.0 - float(np.sum(err**2)) / sst if sst > 0 else float("nan"),
        "mape_pct": float(np.mean(np.abs(err) / np.maximum(np.abs(t), 1e-6)) * 100)
        if t.size
        else float("nan"),
        "p95_abs_err_m": float(np.quantile(np.abs(err), 0.95)) if t.size else float("nan"),
        "n": int(t.size),
    }


def detection_metrics(results_by_sim) -> dict:
    """Recall by scenario type, FAR on operational sims (BI-06), delays."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/05_ANOMALY_LOCALISATION.md")


def localisation_metrics(results_by_sim) -> dict:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/05_ANOMALY_LOCALISATION.md")
