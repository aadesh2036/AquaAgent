"""Smoke-test a running predictor service: §7.9 schema, parity vs the same artifact in-process, latency.

    python -m ml.serve.smoke --url http://<host>:8001 --artifact s3://…/model.tar.gz --n 50 [--record <path>]

Windows are real 12-step SensorWindows rebuilt from the val features (observed sensors + context only).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx
import numpy as np

from shared.contracts.models import PredictorResponse, SensorWindow


def val_windows(features: Path, art, n: int) -> list[SensorWindow]:
    with np.load(features / "val.npz") as z:
        val = {k: z[k] for k in ("p_obs", "q_obs", "ctx", "sim_time_s", "sim_code", "train_ok")}
    gs, graph = art.gs, art.graph
    flows = sorted(graph["flow_sensors"])
    ends = [
        i
        for i in np.flatnonzero(val["train_ok"])
        if i >= 11 and val["sim_code"][i - 11] == val["sim_code"][i]
    ]
    rng = np.random.Generator(np.random.PCG64(7))
    out = []
    for end in sorted(rng.choice(ends, n, replace=False)):
        steps = []
        for r in range(end - 11, end + 1):
            steps.append(
                {
                    "sim_time_s": int(val["sim_time_s"][r]),
                    "pressure_m": {
                        s: float(val["p_obs"][r, gs.node_order.index(nd)])
                        for s, nd in graph["pressure_sensors"].items()
                    },
                    "flow_lps": {f: float(val["q_obs"][r, i]) for i, f in enumerate(flows)},
                    "context": {
                        "time_of_day_s": int(val["ctx"][r, 0]),
                        "tank_level_m": float(val["ctx"][r, 1]),
                        "pump_status": int(val["ctx"][r, 2]),
                        "pump_flow_lps": float(val["ctx"][r, 3]),
                        "reservoir_head_m": float(val["ctx"][r, 4]),
                    },
                }
            )
        out.append(
            SensorWindow(
                network_id=graph["network_id"], sensor_layout_id=graph["sensor_layout_id"], window=steps
            )
        )
    return out


def max_abs_diff(a: dict, b: dict) -> float:
    d = [
        abs(a["reconstruct"]["pressure_m"][k] - b["reconstruct"]["pressure_m"][k])
        for k in a["reconstruct"]["pressure_m"]
    ]
    d += [
        abs(a["leave_one_out"][s]["predicted_m"] - b["leave_one_out"][s]["predicted_m"])
        for s in a["leave_one_out"]
    ]
    d += [
        abs(a["leave_one_out_flow"][f]["predicted_lps"] - b["leave_one_out_flow"][f]["predicted_lps"])
        for f in a["leave_one_out_flow"]
    ]
    return max(d)


def main(argv: list[str] | None = None) -> int:
    from ml.predictor.predict import load_artifact, predict

    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True, help="predictor base URL, e.g. http://1.2.3.4:8001")
    p.add_argument("--artifact", required=True, help="the artifact the service should be serving (parity)")
    p.add_argument("--features", default="data/features/ds1")
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--record", default="")
    args = p.parse_args(argv)

    art = load_artifact(args.artifact)
    mv = art.meta["model_version"]
    with httpx.Client(base_url=args.url, timeout=10) as c:
        health = c.get("/predictor/health").json()
        assert health["model_version"] == mv, f"service serves {health['model_version']}, expected {mv}"
        lat, diffs = [], []
        for w in val_windows(Path(args.features), art, args.n):
            body = {"model_version": mv, "mode": "leave_one_out", "sensor_window": w.model_dump()}
            t0 = time.perf_counter()
            r = c.post("/predictor/predict", json=body)
            lat.append((time.perf_counter() - t0) * 1000)
            r.raise_for_status()
            remote = PredictorResponse.model_validate(r.json()).model_dump()
            diffs.append(max_abs_diff(remote, predict(w, art, mv).model_dump()))
        leaky = {
            "model_version": mv,
            "mode": "leave_one_out",
            "sensor_window": {"hidden": {"leak_nodes": {}}},
        }
        firewall_status = c.post("/predictor/predict", json=leaky).status_code
    result = {
        "url_kind": "ecs-test-task",
        "model_version": mv,
        "n": len(lat),
        "health": health,
        "client_rtt_ms_p50": round(float(np.percentile(lat, 50)), 1),
        "client_rtt_ms_p95": round(float(np.percentile(lat, 95)), 1),
        "parity_max_abs_diff": float(max(diffs)),
        "schema_valid": True,
        "firewall_rejects_non_window": firewall_status == 422,
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    print(json.dumps(result, indent=1))
    if args.record:
        Path(args.record).parent.mkdir(parents=True, exist_ok=True)
        Path(args.record).write_text(json.dumps(result, indent=1))
    ok = result["parity_max_abs_diff"] <= 1e-5 and result["firewall_rejects_non_window"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
