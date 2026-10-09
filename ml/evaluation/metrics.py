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
    """Recall by scenario type, FAR on operational sims (BI-06), delays (BACKBONE §9.5).

    ``results_by_sim``: DataFrame with one row per simulation and columns ``scenario_type``,
    ``operational`` (bool), ``confirm_idx`` (first ANOMALY step or −1), ``fault_idx`` (first post-fault step
    or −1). Steps are 300 s. A fault sim is *detected* if ANOMALY is first confirmed at or after the fault
    start; a confirmation before the fault start counts as a pre-fault false alarm (and not a detection).
    An operational sim is a *false alarm* if ANOMALY is ever confirmed.
    """
    import numpy as np

    df = results_by_sim
    out: dict = {"far_by_type": {}, "recall_by_type": {}, "median_delay_steps_by_type": {}, "n_by_type": {}}
    for st, g in df.groupby("scenario_type"):
        out["n_by_type"][st] = int(len(g))
        if g.operational.all():
            out["far_by_type"][st] = float((g.confirm_idx >= 0).mean())
            continue
        det = (g.confirm_idx >= g.fault_idx) & (g.fault_idx >= 0)
        out["recall_by_type"][st] = float(det.mean())
        d = (g.confirm_idx - g.fault_idx)[det]
        out["median_delay_steps_by_type"][st] = float(np.median(d)) if len(d) else None
        out.setdefault("prefault_false_alarm_by_type", {})[st] = float(
            ((g.confirm_idx >= 0) & (g.confirm_idx < g.fault_idx)).mean()
        )
    ops = df[df.operational]
    faults = df[~df.operational]
    out["far_operational_sims"] = float((ops.confirm_idx >= 0).mean()) if len(ops) else None
    big = faults[faults.scenario_type.isin(["MEDIUM_LEAK", "LARGE_LEAK", "PIPE_BURST"])]
    out["recall_medium_large_burst"] = (
        float(((big.confirm_idx >= big.fault_idx) & (big.fault_idx >= 0)).mean()) if len(big) else None
    )
    return out


def localisation_metrics(results_by_sim) -> dict:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/05_ANOMALY_LOCALISATION.md")
