"""One-time TEST evaluation of a FROZEN detector (BACKBONE §9.5, G5; module 05 §6 step 4).

    python -m ml.anomaly.evaluate --thresholds data/models/anomaly/<thr>/thresholds.json \
        --predictor data/models/predictor/<mv>/model.tar.gz [--upload]

Reads thresholds.json read-only and refuses to run if its content hash or predictor version do not match.
Labels (scenario type, fault location, severity) are read here only, never by the detector.
Writes data/experiments/<thr>/{metrics_test.json, detection_table_test.csv}.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from ml.anomaly.residuals import SENSORS, loo_residuals, sigma_matrix
from ml.anomaly.rtca import load_thresholds
from ml.anomaly.tune import content_hash, episodes, evaluate_config, load_split

STEP_S = 300


def main(argv: list[str] | None = None) -> int:
    from ml.predictor.predict import load_artifact

    p = argparse.ArgumentParser()
    p.add_argument("--thresholds", required=True)
    p.add_argument("--predictor", required=True)
    p.add_argument("--features", default="data/features/ds1")
    p.add_argument("--processed", default="data/processed/ds1")
    p.add_argument("--split", default="test")
    p.add_argument("--experiments-root", default="data/experiments")
    p.add_argument("--upload", action="store_true")
    p.add_argument("--bucket", default=os.environ.get("AQUA_BUCKET"))
    args = p.parse_args(argv)

    cfg = load_thresholds(args.thresholds)
    if content_hash(cfg) != cfg["content_sha256"]:
        raise SystemExit("thresholds.json content hash mismatch — file was modified after freezing")
    art = load_artifact(args.predictor)
    if art.meta["model_version"] != cfg["predictor_model_version"]:
        raise SystemExit(f"predictor {art.meta['model_version']} != frozen {cfg['predictor_model_version']}")

    data = load_split(Path(args.features), args.split)
    r = loo_residuals(data, art)
    z = r / sigma_matrix(data["ctx"][:, 3].astype(np.float64), cfg["sigma_table"])
    zz, valid, labels = episodes(data, z)
    pr = cfg["params"]
    m, per_sim = evaluate_config(
        zz, valid, labels, pr["k1"], pr["k2"], pr["W"], pr["T"], tuple(cfg["detect_sensors"])
    )

    sc = pd.read_parquet(
        Path(args.processed) / f"split={args.split}" / "scenarios",
        columns=[
            "simulation_id",
            "fault_type",
            "location_kind",
            "location_id",
            "zone_id",
            "severity_bucket",
            "fault_end_s",
        ],
    )
    per_sim = per_sim.merge(sc, on="simulation_id", how="left")
    per_sim["detected"] = (per_sim.confirm_idx >= per_sim.fault_idx) & (per_sim.fault_idx >= 0)
    per_sim["false_alarm"] = per_sim.operational & (per_sim.confirm_idx >= 0)
    per_sim["delay_steps"] = np.where(per_sim.detected, per_sim.confirm_idx - per_sim.fault_idx, np.nan)
    leaks = per_sim[per_sim.fault_type.isin(["LEAK", "BURST"])]
    loc = leaks.location_kind + ":" + leaks.location_id
    hold = leaks[loc.isin(["pipe:5", "junction:6"])]
    m["holdout_locations"] = {
        "n": int(len(hold)),
        "recall": float(hold.detected.mean()) if len(hold) else None,
        "recall_medium_large_burst": float(hold[hold.scenario_type != "SMALL_LEAK"].detected.mean())
        if len(hold)
        else None,
    }
    m["recall_by_severity_bucket"] = {
        k: {"recall": float(g.detected.mean()), "n": int(len(g))} for k, g in leaks.groupby("severity_bucket")
    }
    m["recall_by_zone"] = {
        k: {"recall": float(g.detected.mean()), "n": int(len(g))} for k, g in leaks.groupby("zone_id")
    }
    m["median_delay_s_MEDIUM"] = (
        float(m["median_delay_steps_by_type"]["MEDIUM_LEAK"]) * STEP_S
        if m["median_delay_steps_by_type"].get("MEDIUM_LEAK") is not None
        else None
    )
    out = {
        "split": args.split,
        "thresholds_version": cfg["thresholds_version"],
        "thresholds_sha256": cfg["content_sha256"],
        "predictor_model_version": cfg["predictor_model_version"],
        "params": pr,
        "detect_sensors": cfg["detect_sensors"],
        "n_sims": int(len(per_sim)),
        "definitions": {
            "detected": "ANOMALY first confirmed at or after the fault start (300-s steps)",
            "false_alarm": "operational sim with ANOMALY confirmed at any time",
            "delay": "steps from fault start to confirmation",
        },
        **m,
    }
    exp = Path(args.experiments_root) / cfg["thresholds_version"]
    exp.mkdir(parents=True, exist_ok=True)
    (exp / f"metrics_{args.split}.json").write_text(json.dumps(out, indent=1, default=float))
    per_sim.to_csv(exp / f"detection_table_{args.split}.csv", index=False)
    print(json.dumps(out, indent=1, default=float))
    if args.upload:
        if not args.bucket:
            raise SystemExit("--upload needs AQUA_BUCKET")
        subprocess.run(
            [
                "aws",
                "s3",
                "sync",
                str(exp),
                f"s3://{args.bucket}/experiments/{cfg['thresholds_version']}/",
                "--only-show-errors",
            ],
            check=True,
        )
    return 0


assert len(SENSORS) == 5

if __name__ == "__main__":
    raise SystemExit(main())
