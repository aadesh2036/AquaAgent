"""Deployable SensorSetNet detector: freeze, streaming inference, one-time test evaluation (P-05-2).

    python -m ml.anomaly.sensorset freeze   --selection data/experiments/detsel_gnn --predictor <mv> [--upload]
    python -m ml.anomaly.sensorset evaluate --detector data/models/anomaly/<thr>/ --predictor <tar.gz> [--upload]

Artifact ``data/models/anomaly/<thr_ds1_ts>/``: ``model.pt`` + ``detector.json`` (σ per sensor, history,
τ, T, context scalers, predictor version, val metrics, content SHA-256). Sensor TYPE comes from the id prefix
(S* = pressure, F* = flow, BACKBONE §5.1) — no sensor identity reaches the model.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import torch

from ml.anomaly.setnet import SENSOR_TYPES, SensorSetNet, context_features
from shared.contracts.ids import thresholds_version
from shared.contracts.models import AnomalyResult, AnomalyStatus, ResidualFrame, WindowContext

STEP_S = 300


def _hash(cfg: dict, weights: bytes) -> str:
    body = {k: v for k, v in cfg.items() if k != "content_sha256"}
    h = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode())
    h.update(weights)
    return "sha256:" + h.hexdigest()


def _read(uri: str, name: str) -> bytes:
    if uri.startswith("s3://"):
        import boto3

        bucket, key = uri[5:].rstrip("/").split("/", 1)
        return boto3.client("s3").get_object(Bucket=bucket, Key=f"{key}/{name}")["Body"].read()
    return (Path(uri) / name).read_bytes()


class SensorSetDetector:
    """Streaming detector: ``update(frame, context) -> AnomalyResult``.

    ANOMALY holds while the alarm persists; it keeps scoring every step and clears itself after
    ``clear_after_steps`` consecutive steps with P ≤ τ (default 6 = 30 min of normal readings).
    ``clear_after_steps=None`` = latch until ``reset()`` (evaluation semantics: first confirmation).
    """

    def __init__(self, model: SensorSetNet, cfg: dict, clear_after_steps: int | None = 6) -> None:
        self.model, self.cfg = model.eval(), cfg
        self.clear_after = clear_after_steps
        self.h, self.tau, self.t = cfg["history"], cfg["params"]["tau"], cfg["params"]["T"]
        self.version = cfg["thresholds_version"]
        self.reset()

    @classmethod
    def load(cls, uri: str) -> SensorSetDetector:
        """``uri`` = local artifact dir or ``s3://…/models/anomaly/<thr>/``; verifies the content hash."""
        cfg = json.loads(_read(uri, "detector.json"))
        weights = _read(uri, "model.pt")
        if _hash(cfg, weights) != cfg["content_sha256"]:
            raise ValueError("detector artifact hash mismatch")
        model = SensorSetNet(hidden=cfg["hidden"], history=cfg["history"])
        model.load_state_dict(torch.load(io.BytesIO(weights), map_location="cpu", weights_only=True))
        return cls(model, cfg)

    def reset(self) -> None:
        self._z: dict[str, deque] = {}
        self._ctx: deque = deque(maxlen=self.h)
        self._streak, self._start = 0, None
        self._confirmed: AnomalyResult | None = None
        self._calm = 0  # consecutive P ≤ τ steps while confirmed

    @torch.no_grad()
    def score(self) -> tuple[float, dict[str, float]]:
        sensors = sorted(self._z)
        n = len(self._ctx)
        x = np.zeros((1, len(sensors), self.h, 1 + len(SENSOR_TYPES) + 4), np.float32)
        ctx = np.array(self._ctx, np.float32)
        for i, s in enumerate(sensors):
            hist = list(self._z[s])
            x[0, i, self.h - len(hist) :, 0] = hist
            x[0, i, :, 1 + SENSOR_TYPES.index("pressure" if s.startswith("S") else "flow")] = 1.0
            x[0, i, self.h - n :, 1 + len(SENSOR_TYPES) :] = ctx
        logit, w = self.model(torch.from_numpy(x), torch.ones(1, len(sensors), dtype=torch.bool))
        return float(torch.sigmoid(logit)[0]), dict(zip(sensors, map(float, w[0]), strict=True))

    def update(self, frame: ResidualFrame, context: WindowContext) -> AnomalyResult:
        if not isinstance(frame, ResidualFrame) or not isinstance(context, WindowContext):
            raise TypeError("update takes a ResidualFrame + WindowContext only (§11)")
        if self._confirmed is not None and self.clear_after is None:
            return self._confirmed
        sig = self.cfg["sigmas"]
        for s, r in frame.residuals.items():
            if s in sig:
                self._z.setdefault(s, deque([0.0] * len(self._ctx), maxlen=self.h)).append(r / sig[s])
        for s in self._z:  # missing reading this step → 0 (no evidence), keeps histories aligned
            if s not in frame.residuals:
                self._z[s].append(0.0)
        raw = np.array(
            [
                [
                    context.time_of_day_s,
                    context.tank_level_m or 0.0,
                    context.pump_status or 0,
                    context.pump_flow_lps or 0.0,
                    context.reservoir_head_m or 0.0,
                ]
            ],
            np.float64,
        )
        self._ctx.append(context_features(raw, self.cfg["context_scalers"])[0])
        p, att = self.score()
        t = frame.sim_time_s
        if p > self.tau:
            self._start = t if self._streak == 0 else self._start
            self._streak += 1
        else:
            self._streak, self._start = 0, None
        driving = [s for s, a in sorted(att.items(), key=lambda kv: -kv[1]) if a >= 1.0 / len(att)]
        if self._confirmed is not None:  # alarm active: keep listening, clear after sustained normal
            self._calm = 0 if p > self.tau else self._calm + 1
            if self._calm >= self.clear_after:
                self._confirmed, self._calm = None, 0
                self._streak, self._start = 0, None
                return AnomalyResult(
                    status=AnomalyStatus.NORMAL, anomaly_score=round(p, 4), thresholds_version=self.version
                )
            self._confirmed = self._confirmed.model_copy(update={"anomaly_score": round(p, 4)})
            return self._confirmed
        if self._streak >= self.t:
            self._confirmed = AnomalyResult(
                status=AnomalyStatus.ANOMALY,
                anomaly_score=round(p, 4),
                first_flag_time_s=self._start,
                confirmed_time_s=t,
                detection_delay_steps=(t - self._start) // STEP_S,
                driving_sensors=driving,
                residual_history_ref=f"detector buffer last {self.h} frames",
                thresholds_version=self.version,
            )
            return self._confirmed
        return AnomalyResult(
            status=AnomalyStatus.WATCH if p > self.tau else AnomalyStatus.NORMAL,
            anomaly_score=round(p, 4),
            first_flag_time_s=self._start,
            driving_sensors=driving if p > self.tau else [],
            thresholds_version=self.version,
        )


# ------------------------------------------------------------------------------------------- CLI
def _episodes_for(split, predictor, feat, proc, sig):
    from ml.anomaly.select import ep
    from ml.anomaly.tune import load_split

    scalers = json.loads((feat / "scalers.json").read_text())
    a = load_split(feat, split)
    r = np.load(feat / "residuals" / f"{predictor}_{split}.npy").astype(np.float64)
    zz, valid, lab = ep(a, r / sig)
    cx, _, _ = ep(a, context_features(a["ctx"].astype(np.float64), scalers))
    return zz[..., None], cx, valid, lab, a


def freeze(args) -> int:
    import pandas as pd

    from ml.anomaly.residuals import SENSORS
    from ml.anomaly.tune import load_split

    feat, sel = Path(args.features), Path(args.selection)
    row = pd.read_csv(sel / "selection_val.csv").set_index("model").loc["R3_sensorset_generalised"]
    tr = load_split(feat, "train")
    res_tr = np.load(feat / "residuals" / f"{args.predictor}_train.npy").astype(np.float64)
    sig = res_tr[tr["train_ok"]].std(0)
    scalers = json.loads((feat / "scalers.json").read_text())
    tv = thresholds_version("ds1")
    cfg = {
        "schema_version": "1.0",
        "thresholds_version": tv,
        "detector": "sensorset_tcn_v1",
        "created_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "predictor_model_version": args.predictor,
        "dataset_version": "ds1",
        "sigmas": {s: float(v) for s, v in zip(SENSORS, sig, strict=True)},
        "sigma_source": "std of LOO residuals, train-split normal rows",
        "history": 24,
        "hidden": 32,
        "step_s": STEP_S,
        "params": {"tau": float(row["tau"]), "T": int(row["T"])},
        "alarm_rule": "P(anomaly) > tau for T consecutive steps → ANOMALY (latched until reset)",
        "context_scalers": {k: scalers[k] for k in ("pump_flow_lps", "tank_level_m")},
        "trained_on": "train split (labels: LEAK/BURST active fault_start ≤ t < fault_end); tau/T chosen on val",
        "selection": str(sel / "selection_val.csv"),
        "val_metrics": {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()},
        "code_git_sha": subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
    }
    weights = (sel / "sensorset_candidate.pt").read_bytes()
    cfg["content_sha256"] = _hash(cfg, weights)
    out = Path(args.out_root) / tv
    out.mkdir(parents=True, exist_ok=True)
    (out / "model.pt").write_bytes(weights)
    (out / "detector.json").write_text(json.dumps(cfg, indent=1, sort_keys=True, default=float))
    print(f"[freeze] {out}  {cfg['content_sha256']}  params={cfg['params']}")
    return 0


def evaluate(args) -> int:
    import pandas as pd

    from ml.anomaly.select import predict_set
    from ml.evaluation.metrics import detection_metrics

    det = SensorSetDetector.load(args.detector)
    cfg = det.cfg
    feat, proc = Path(args.features), Path(args.processed)
    sig = np.array([cfg["sigmas"][s] for s in ("S1", "S2", "S3", "F1", "F2")])
    zz, cx, valid, lab, _ = _episodes_for(args.split, cfg["predictor_model_version"], feat, proc, sig)
    p = predict_set(det.model, zz, cx, valid, cfg["history"])
    from ml.anomaly.rtca import run_batch

    c, _ = run_batch(p[..., None], valid, cfg["params"]["tau"], -1.0, 1, cfg["params"]["T"])
    per_sim = lab.assign(confirm_idx=c)
    m = detection_metrics(per_sim)
    sc = pd.read_parquet(
        proc / f"split={args.split}" / "scenarios",
        columns=["simulation_id", "fault_type", "location_kind", "location_id", "severity_bucket"],
    )
    per_sim = per_sim.merge(sc, on="simulation_id", how="left")
    per_sim["detected"] = (per_sim.confirm_idx >= per_sim.fault_idx) & (per_sim.fault_idx >= 0)
    leaks = per_sim[per_sim.fault_type.isin(["LEAK", "BURST"])]
    hold = leaks[(leaks.location_kind + ":" + leaks.location_id).isin(["pipe:5", "junction:6"])]
    m["holdout_locations"] = {
        "n": int(len(hold)),
        "recall": float(hold.detected.mean()) if len(hold) else None,
        "recall_medium_large_burst": float(hold[hold.scenario_type != "SMALL_LEAK"].detected.mean()),
    }
    m["recall_by_severity_bucket"] = {
        k: {"recall": float(g.detected.mean()), "n": int(len(g))} for k, g in leaks.groupby("severity_bucket")
    }
    out = {
        "split": args.split,
        "thresholds_version": cfg["thresholds_version"],
        "detector": cfg["detector"],
        "content_sha256": cfg["content_sha256"],
        "predictor_model_version": cfg["predictor_model_version"],
        "params": cfg["params"],
        "n_sims": int(len(per_sim)),
        **m,
    }
    exp = Path(args.experiments_root) / cfg["thresholds_version"]
    exp.mkdir(parents=True, exist_ok=True)
    (exp / f"metrics_{args.split}.json").write_text(json.dumps(out, indent=1, default=float))
    per_sim.to_csv(exp / f"detection_table_{args.split}.csv", index=False)
    print(json.dumps(out, indent=1, default=float))
    return 0


def upload(local: Path, bucket: str, kind: str) -> None:
    subprocess.run(
        ["aws", "s3", "sync", str(local), f"s3://{bucket}/{kind}/{local.name}/", "--only-show-errors"],
        check=True,
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["freeze", "evaluate"])
    p.add_argument("--selection", default="data/experiments/detsel_gnn")
    p.add_argument("--predictor", default="gnn_ds1_202610090559")
    p.add_argument("--detector", default="")
    p.add_argument("--features", default="data/features/ds1")
    p.add_argument("--processed", default="data/processed/ds1")
    p.add_argument("--split", default="test")
    p.add_argument("--out-root", default="data/models/anomaly")
    p.add_argument("--experiments-root", default="data/experiments")
    args = p.parse_args(argv)
    torch.set_num_threads(10)
    return freeze(args) if args.cmd == "freeze" else evaluate(args)


if __name__ == "__main__":
    raise SystemExit(main())
