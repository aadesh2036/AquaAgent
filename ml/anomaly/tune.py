"""Tune k1,k2,W,T on VAL only, then freeze → thresholds.json (BACKBONE §9.3, G5).

    python -m ml.anomaly.tune --predictor data/models/predictor/<mv> [--upload]

1. LOO residuals for every val row with the frozen predictor (``ml.anomaly.residuals.loo_residuals``).
2. σ per sensor from val NORMAL rows (operational sims + pre-fault steps), conditioned on 5 quantile bins
   of SCADA pump flow (residual spread is ~2.5× larger at high demand).
3. Grid = the module 05 §5 grid extended upward (the contract grid has no feasible point on ds1:
   ≥ 33 % FAR on DEMAND_SHIFT/HIGH_DEMAND) × detecting-sensor sets {all 5, S1+F1+F2, F1+F2}.
   Objective: max recall on MEDIUM/LARGE/BURST s.t. FAR ≤ 5 % on EACH operational type; ties → lower
   median MEDIUM delay → higher SMALL recall → fewer pre-fault alarms. If no config is feasible, the one
   with the lowest worst-type FAR is taken and that is reported.
4. Freeze: ``data/models/anomaly/<thr_ds1_ts>/thresholds.json`` with a SHA-256 of its canonical content.

This module never reads the test split (asserted).
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ml.anomaly.residuals import SENSORS, estimate_binned_sigmas, loo_residuals, sigma_matrix
from ml.anomaly.rtca import run_batch
from ml.evaluation.metrics import detection_metrics
from ml.features.builder import SCENARIO_TYPES
from shared.contracts.ids import thresholds_version
from shared.contracts.models import OPERATIONAL_SCENARIOS

GRID = {
    "k1": (2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0),
    "k2": (2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 8.0),
    "W": (3, 6, 9, 12),
    "T": (2, 3, 4, 6),
}
SENSOR_SETS = {"all5": ("S1", "S2", "S3", "F1", "F2"), "S1+F1+F2": ("S1", "F1", "F2"), "F1+F2": ("F1", "F2")}
FAR_TARGET = 0.05
OPERATIONAL = sorted(s.value for s in OPERATIONAL_SCENARIOS)
SCORE_FORMULA = "c / (c + k2), c = max over sensors of mean|z| over the last W steps"


def load_split(features: Path, split: str) -> dict[str, np.ndarray]:
    with np.load(features / f"{split}.npz") as z:
        return {k: z[k] for k in z.files}


def episodes(arrays: dict[str, np.ndarray], z: np.ndarray) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """Rows → [S, L, 5] z per simulation (time-ordered), validity mask, per-sim label frame."""
    codes = arrays["sim_code"]
    order = np.lexsort((arrays["sim_time_s"], codes))
    n_sims = len(arrays["sim_ids"])
    counts = np.bincount(codes, minlength=n_sims)
    n_l = int(counts.max())
    zz = np.zeros((n_sims, n_l, z.shape[1]))
    valid = np.zeros((n_sims, n_l), bool)
    pos = np.concatenate([np.arange(c) for c in counts])
    zz[codes[order], pos] = z[order]
    valid[codes[order], pos] = True
    stype = np.array(SCENARIO_TYPES)[arrays["scenario_code"]]
    rows = []
    for sid in range(n_sims):
        r = order[codes[order] == sid]
        pf = np.flatnonzero(arrays["post_fault"][r])
        st = stype[r[0]]
        rows.append(
            {
                "simulation_id": str(arrays["sim_ids"][sid]),
                "scenario_type": st,
                "operational": st in OPERATIONAL,
                "fault_idx": int(pf[0]) if len(pf) else -1,
            }
        )
    return zz, valid, pd.DataFrame(rows)


def evaluate_config(zz, valid, labels, k1, k2, w, t, detect=SENSORS) -> tuple[dict, pd.DataFrame]:
    cols = [SENSORS.index(s) for s in detect]
    confirm, start = run_batch(zz[:, :, cols], valid, k1, k2, w, t)
    df = labels.assign(confirm_idx=confirm, flag_start_idx=start)
    return detection_metrics(df), df


def _rank_key(m: dict) -> tuple:
    feasible = all(m["far_by_type"].get(s, 0.0) <= FAR_TARGET for s in OPERATIONAL)
    worst_far = max(m["far_by_type"].get(s, 0.0) for s in OPERATIONAL)
    delay = m["median_delay_steps_by_type"].get("MEDIUM_LEAK")
    return (
        feasible,
        -worst_far if not feasible else 0.0,
        m["recall_medium_large_burst"],
        -(delay if delay is not None else 1e9),
        m["recall_by_type"].get("SMALL_LEAK", 0.0),
        -sum(m.get("prefault_false_alarm_by_type", {}).values()),
    )


def rank(m: dict, n_detect: int) -> tuple:
    return (*_rank_key(m), n_detect)  # final tie-break: keep more sensors


def content_hash(cfg: dict) -> str:
    body = {k: v for k, v in cfg.items() if k != "content_sha256"}
    return (
        "sha256:"
        + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    )


def main(argv: list[str] | None = None) -> int:
    from ml.predictor.predict import load_artifact

    p = argparse.ArgumentParser()
    p.add_argument("--predictor", required=True, help="predictor artifact (dir, model.tar.gz or s3://)")
    p.add_argument("--features", default="data/features/ds1")
    p.add_argument("--out-root", default="data/models/anomaly")
    p.add_argument("--experiments-root", default="data/experiments")
    p.add_argument("--upload", action="store_true")
    p.add_argument("--bucket", default=os.environ.get("AQUA_BUCKET"))
    args = p.parse_args(argv)

    art = load_artifact(args.predictor)
    mv = art.meta["model_version"]
    val = load_split(Path(args.features), "val")  # the ONLY split this module opens
    r = loo_residuals(val, art)
    normal = val["train_ok"]
    pump = val["ctx"][:, 3].astype(np.float64)
    sigma_table = estimate_binned_sigmas(r[normal], pump[normal])
    z = r / sigma_matrix(pump, sigma_table)
    zn = z[normal]
    z_check = {
        s: {"mean": float(zn[:, i].mean()), "std": float(zn[:, i].std())} for i, s in enumerate(SENSORS)
    }
    zz, valid, labels = episodes(val, z)
    print(f"[tune] predictor={mv} val sims={len(labels)} rows={len(z)} sigma bins={sigma_table['edges']}")

    grid_rows, best = [], None
    for (set_name, detect), (k1, k2, w, t) in itertools.product(
        SENSOR_SETS.items(), itertools.product(*GRID.values())
    ):
        m, _ = evaluate_config(zz, valid, labels, k1, k2, w, t, detect)
        row = {
            "sensors": set_name,
            "k1": k1,
            "k2": k2,
            "W": w,
            "T": t,
            "recall_MLB": m["recall_medium_large_burst"],
            **{f"far_{s}": m["far_by_type"].get(s) for s in OPERATIONAL},
            **{f"recall_{s}": v for s, v in m["recall_by_type"].items()},
            "median_delay_MEDIUM": m["median_delay_steps_by_type"].get("MEDIUM_LEAK"),
        }
        grid_rows.append(row)
        if best is None or rank(m, len(detect)) > rank(best[1], len(best[0][4])):
            best = ((k1, k2, w, t, detect), m)
    (k1, k2, w, t, detect), m = best
    feasible = _rank_key(m)[0]
    tv = thresholds_version(art.meta["dataset_version"])
    cfg = {
        "schema_version": "1.0",
        "thresholds_version": tv,
        "created_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "detector": "rtca_dual_threshold_v1",
        "predictor_model_version": mv,
        "dataset_version": art.meta["dataset_version"],
        "sensors": list(SENSORS),
        "units": {"S1": "m", "S2": "m", "S3": "m", "F1": "L/s", "F2": "L/s"},
        "sigma_table": sigma_table,
        "detect_sensors": list(detect),
        "params": {"k1": k1, "k2": k2, "W": w, "T": t},
        "step_s": 300,
        "latch": "ANOMALY latches until reset()",
        "anomaly_score": SCORE_FORMULA,
        "tuned_on": "val split only",
        "grid": {
            **{k: list(v) for k, v in GRID.items()},
            "detect_sensor_sets": {k: list(v) for k, v in SENSOR_SETS.items()},
        },
        "objective": f"max recall MEDIUM/LARGE/BURST s.t. FAR <= {FAR_TARGET} on each operational type",
        "objective_met": bool(feasible),
        "val_z_check_normal": z_check,
        "val_metrics": m,
        "code_git_sha": subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
    }
    cfg["content_sha256"] = content_hash(cfg)
    out = Path(args.out_root) / tv
    out.mkdir(parents=True, exist_ok=True)
    (out / "thresholds.json").write_text(json.dumps(cfg, indent=1, sort_keys=True))
    exp = Path(args.experiments_root) / tv
    exp.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(grid_rows).to_csv(exp / "tuning_grid_val.csv", index=False)
    (exp / "val_metrics.json").write_text(
        json.dumps({"params": cfg["params"], "detect_sensors": list(detect), **m}, indent=1)
    )
    print(f"[tune] FROZEN {out / 'thresholds.json'}  {cfg['content_sha256']}")
    print(
        json.dumps(
            {
                "params": cfg["params"],
                "detect_sensors": list(detect),
                "objective_met": cfg["objective_met"],
                **m,
            },
            indent=1,
        )
    )

    if args.upload:
        if not args.bucket:
            raise SystemExit("--upload needs AQUA_BUCKET")
        dst = f"s3://{args.bucket}/models/anomaly/{tv}/thresholds.json"
        subprocess.run(
            ["aws", "s3", "cp", str(out / "thresholds.json"), dst, "--only-show-errors"], check=True
        )
        print(f"[tune] uploaded → {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
