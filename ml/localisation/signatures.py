"""Physics leak signatures from the network model (BACKBONE §9.4, T2c; owner request 2026-10-09).

    python -m ml.localisation.signatures --predictor <model.tar.gz> --detector <anomaly artifact dir> [--upload]

For every candidate location (§8.2: junctions 2–7, pipes 1–8 at mid-pipe) × leak size × time of day:
simulate the leak on the KNOWN network (sim engine), turn each snapshot into sensor readings with the same
``snapshot_to_step`` the live api uses, run the same predictor + LOO residuals, normalise with the detector's
σ, and store the mean z-vector over the first hour after onset. No labelled field leaks are needed, so every
location — including ones never seen in training — has a signature; a new city only needs its own map.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from shared.contracts.ids import signatures_version

AREAS_M2 = {"MEDIUM": 1.414e-4, "LARGE": 3.873e-4, "BURST": 1.732e-3}  # geometric midpoints, ds1.yaml
START_H = (3, 9, 15, 21)
HORIZON_STEPS = 12  # first hour after onset (300-s steps)


def generate(predictor: str, detector_dir: str, out_root: str) -> Path:
    from ml.anomaly.residuals import residual_frame
    from ml.anomaly.sensorset import SensorSetDetector
    from ml.features.online import snapshot_to_step
    from ml.predictor.predict import load_artifact, predict
    from shared.contracts.models import (
        WINDOW_STEPS,
        FaultSpec,
        FaultType,
        LocationKind,
        NetworkConfig,
        ScenarioType,
        SensorWindow,
    )
    from sim.generate.runner import load_config, load_sensor_layout, simulate
    from sim.scenarios.sampler import make_rng, sample_scenario

    art = load_artifact(predictor)
    det = SensorSetDetector.load(detector_dir)
    sig = det.cfg["sigmas"]
    gen = load_config("config/generation/ds1.yaml")
    layout = load_sensor_layout(gen["sensor_layout_id"])
    net = NetworkConfig.model_validate(
        json.loads(Path(f"config/networks/{gen['network_id']}.json").read_text())
    )
    zone = {("junction", n.node_id): n.zone_id for n in net.nodes} | {
        ("pipe", lk.link_id): lk.zone_id for lk in net.links
    }
    locs = [("junction", j) for j in gen["fault_locations"]["junctions"]] + [
        ("pipe", p) for p in gen["fault_locations"]["pipes"]
    ]

    rows = []
    for k, start_h in enumerate(START_H):
        base = sample_scenario(ScenarioType.NORMAL, 900000 + k, "sig", make_rng(20261009 + k), gen)
        for kind, loc in locs:
            for size, area in AREAS_M2.items():
                start_s = start_h * 3600
                f = FaultSpec(
                    fault_id="f0",
                    fault_type=FaultType.BURST if size == "BURST" else FaultType.LEAK,
                    location_kind=LocationKind(kind),
                    location_id=loc,
                    position=0.5 if kind == "pipe" else None,
                    leak_area_m2=area,
                    discharge_coeff=0.75,
                    start_s=start_s,
                    end_s=None,
                )
                spec = base.model_copy(
                    update={"faults": [f], "duration_s": start_s + (HORIZON_STEPS + 2) * 300}
                )
                snaps = simulate(spec)
                steps = [snapshot_to_step(s, layout) for s in snaps]
                onset = start_s // 300
                zs = []
                for t in range(onset + 1, onset + 1 + HORIZON_STEPS):
                    w = SensorWindow(
                        network_id=net.network_id,
                        sensor_layout_id=layout.sensor_layout_id,
                        window=steps[max(0, t - WINDOW_STEPS + 1) : t + 1],
                    )
                    fr = residual_frame(w, predict(w, art, art.meta["model_version"]), sig)
                    zs.append([fr.z[s] for s in ("S1", "S2", "S3", "F1", "F2")])
                rows.append(
                    {
                        "location_kind": kind,
                        "location_id": loc,
                        "zone_id": zone[(kind, loc)],
                        "size": size,
                        "start_h": start_h,
                        "z_mean": np.mean(zs, 0).round(4).tolist(),
                    }
                )
        print(f"[signatures] start {start_h:02d}:00 done ({len(rows)} signatures)", flush=True)

    sv = signatures_version("ds1")
    out = Path(out_root) / sv
    out.mkdir(parents=True, exist_ok=True)
    doc = {
        "schema_version": "1.0",
        "signatures_version": sv,
        "created_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": "signature_cosine_v1",
        "network_id": net.network_id,
        "sensors": ["S1", "S2", "S3", "F1", "F2"],
        "predictor_model_version": art.meta["model_version"],
        "detector_version": det.version,
        "sigmas": sig,
        "horizon_steps": HORIZON_STEPS,
        "areas_m2": AREAS_M2,
        "start_h": list(START_H),
        "signatures": rows,
    }
    (out / "signatures.json").write_text(json.dumps(doc, indent=1))
    print(f"[signatures] wrote {out / 'signatures.json'} ({len(rows)})")
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--predictor", required=True)
    p.add_argument("--detector", required=True)
    p.add_argument("--out-root", default="data/models/localisation")
    p.add_argument("--upload", action="store_true")
    p.add_argument("--bucket", default=os.environ.get("AQUA_BUCKET"))
    args = p.parse_args(argv)
    out = generate(args.predictor, args.detector, args.out_root)
    if args.upload:
        subprocess.run(
            [
                "aws",
                "s3",
                "sync",
                str(out),
                f"s3://{args.bucket}/models/localisation/{out.name}/",
                "--only-show-errors",
            ],
            check=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
