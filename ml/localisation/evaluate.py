"""Offline localisation accuracy of a signatures artifact on a features split (BACKBONE §9.4, T2c).

    python -m ml.localisation.evaluate --signatures <dir|s3://…> --features data/features/ds3 \
        --processed data/processed/ds3 --split test [--out data/experiments/<sig>/]

Same protocol as the ds1 numbers in TILL_NOW (onset known): for every MEDIUM/LARGE/BURST sim, the mean
z-vector over the first ``horizon_steps`` steps after the true fault start (residuals from the
signatures' predictor, σ from the signatures doc) is ranked by ``SignatureMatcher``; top-1 / top-3 pipe or
junction hit and probable-zone hit are reported overall, by type and for the holdout locations.
Residuals are read from ``<features>/residuals/<predictor>_<split>.npy`` (written by the detector job).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.localisation.matcher import SENSORS, SignatureMatcher

STEP_S = 300
TYPES = ("MEDIUM_LEAK", "LARGE_LEAK", "PIPE_BURST")


def evaluate(
    matcher: SignatureMatcher, features: Path, processed: Path, split: str, holdout: list[str]
) -> dict:
    doc = matcher.doc
    with np.load(features / f"{split}.npz", allow_pickle=False) as z:
        sim_code, sim_ids, t_s = z["sim_code"], z["sim_ids"], z["sim_time_s"]
    res = np.load(features / "residuals" / f"{doc['predictor_model_version']}_{split}.npy")
    zz = res / np.array([doc["sigmas"][s] for s in SENSORS])
    sc = pd.read_parquet(
        processed / f"split={split}" / "scenarios",
        columns=[
            "simulation_id",
            "scenario_type",
            "fault_start_s",
            "location_kind",
            "location_id",
            "zone_id",
        ],
    )
    sc = sc[sc.scenario_type.isin(TYPES)]
    code_of = {str(s): i for i, s in enumerate(sim_ids)}
    h = int(doc["horizon_steps"])
    rows = []
    for r in sc.itertuples():
        rows_i = np.flatnonzero(sim_code == code_of[r.simulation_id])
        onset = int(r.fault_start_s // STEP_S)
        steps = t_s[rows_i] // STEP_S
        sel = rows_i[(steps >= onset + 1) & (steps <= onset + h)]
        if len(sel) == 0:
            continue
        out = matcher.rank(zz[sel].mean(0), top_k=3)
        ids = [(c.location_kind, c.location_id) for c in out.candidates]
        truth = (r.location_kind, r.location_id)
        rows.append(
            {
                "simulation_id": r.simulation_id,
                "scenario_type": r.scenario_type,
                "truth": f"{r.location_kind}:{r.location_id}",
                "top1": ids[0] == truth,
                "top3": truth in ids,
                "zone": out.probable_zone.zone_id == r.zone_id,
                "holdout": f"{r.location_kind}:{r.location_id}" in holdout,
            }
        )
    df = pd.DataFrame(rows)

    def acc(d: pd.DataFrame) -> dict:
        return {
            "n": int(len(d)),
            **({k: round(float(d[k].mean()), 4) for k in ("top1", "top3", "zone")} if len(d) else {}),
        }

    return {
        "split": split,
        "signatures_version": doc["signatures_version"],
        "predictor_model_version": doc["predictor_model_version"],
        "protocol": f"onset known; mean z over steps onset+1..onset+{h}; cosine match",
        "overall": acc(df),
        "by_type": {t: acc(df[df.scenario_type == t]) for t in TYPES},
        "holdout_locations": acc(df[df.holdout]),
        "never_holdout": acc(df[~df.holdout]),
        "_table": df,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--signatures", required=True)
    p.add_argument("--features", required=True)
    p.add_argument("--processed", required=True)
    p.add_argument("--split", default="test")
    p.add_argument("--holdout", default="pipe:5,junction:6")
    p.add_argument("--out", default="")
    args = p.parse_args(argv)
    m = evaluate(
        SignatureMatcher.load(args.signatures),
        Path(args.features),
        Path(args.processed),
        args.split,
        args.holdout.split(","),
    )
    table = m.pop("_table")
    print(json.dumps(m, indent=1))
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"localisation_{args.split}.json").write_text(json.dumps(m, indent=1))
        table.to_csv(out / f"localisation_table_{args.split}.csv", index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
