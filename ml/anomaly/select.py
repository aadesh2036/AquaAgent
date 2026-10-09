"""Detector model selection on VAL (module 05, P-05-2). Test is never read here.

    python -m ml.anomaly.select --predictor gnn_ds1_202610090559 [--out data/experiments/detsel_<ts>]

Candidates (same alarm rule family, same objective: max recall MEDIUM/LARGE/BURST s.t. FAR ≤ 5 % on each
operational type, ties → lower median MEDIUM delay):
  R1  RTCA dual threshold on LOO z (σ in pump-flow bins, val-tuned) — no learning
  R2  gradient-boosted trees on hand-made window features per fixed sensor slot — fixed-layout REFERENCE
  R3  SensorSetNet — topology-agnostic supervised set model (ml/anomaly/setnet.py) — the generalised target
Learned models (R2, R3) train on the TRAIN split (labels: fault_start ≤ t < fault_end); val picks τ, T.
"""

from __future__ import annotations

import argparse
import itertools
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from ml.anomaly.residuals import SENSORS, estimate_binned_sigmas, sigma_matrix
from ml.anomaly.rtca import run_batch
from ml.anomaly.setnet import SensorSetNet, context_features
from ml.anomaly.tune import GRID, OPERATIONAL, SENSOR_SETS, _rank_key, episodes, evaluate_config, load_split
from ml.evaluation.metrics import detection_metrics

STEP_S = 300
TYPES = ["pressure"] * 3 + ["flow"] * 2


def labels_for(split: str, processed: Path, lab: pd.DataFrame, n_l: int) -> np.ndarray:
    """[E, T] 1 where a LEAK/BURST is active (fault_start ≤ t < fault_end)."""
    sc = pd.read_parquet(
        processed / f"split={split}" / "scenarios",
        columns=["simulation_id", "fault_type", "fault_start_s", "fault_end_s"],
    ).set_index("simulation_id")
    y = np.zeros((len(lab), n_l), np.float32)
    for i, sid in enumerate(lab.simulation_id):
        r = sc.loc[sid]
        if r.fault_type in ("LEAK", "BURST"):
            end = n_l if pd.isna(r.fault_end_s) else int(r.fault_end_s // STEP_S)
            y[i, int(r.fault_start_s // STEP_S) : end] = 1
    return y


def ep(arrays, x):
    zz, valid, lab = episodes(arrays, x)
    return zz, valid, lab


def tune_prob(p: np.ndarray, valid, lab) -> tuple[dict, dict]:
    """τ/T grid for a probability stream p [E, T] with the RTCA streak rule (W=1, k2 off)."""
    best = None
    taus = np.unique(np.quantile(p[valid], [0.9, 0.95, 0.98, 0.99, 0.995, 0.998, 0.999, 0.9995]))
    taus = np.unique(np.concatenate([taus, [0.5, 0.7, 0.8, 0.9, 0.95, 0.98, 0.99]]))
    for tau, t in itertools.product(taus, (1, 2, 3, 4, 6)):
        c, _ = run_batch(p[..., None], valid, tau, -1.0, 1, t)
        m = detection_metrics(lab.assign(confirm_idx=c))
        if best is None or _rank_key(m) > _rank_key(best[1]):
            best = ({"tau": float(tau), "T": t}, m)
    return best


# ---------------------------------------------------------------- R2 features
def window_feats(zz: np.ndarray, ctx: np.ndarray) -> np.ndarray:
    """[E, T, F] per-step features from fixed sensor slots (reference model only)."""
    e, t, s = zz.shape
    cs = np.concatenate([np.zeros((e, 1, s)), np.cumsum(zz, 1)], 1)
    ca = np.concatenate([np.zeros((e, 1, s)), np.cumsum(np.abs(zz), 1)], 1)

    def mean_last(c, k):
        idx = np.arange(1, t + 1)
        lo = np.maximum(idx - k, 0)
        return (c[:, idx] - c[:, lo]) / (idx - lo)[None, :, None]

    feats = [zz, mean_last(cs, 3), mean_last(cs, 6), mean_last(cs, 12), mean_last(ca, 6), mean_last(ca, 24)]
    step = mean_last(cs, 6) - np.concatenate([np.zeros((e, 18, s)), mean_last(cs, 6)[:, :-18]], 1)
    feats.append(step)
    return np.concatenate(feats + [ctx], axis=-1).astype(np.float32)


# ---------------------------------------------------------------- R3 training
def gather(zp, cp, typ, e_idx, t_idx, h):
    """zp [E, T+H-1, S, K] per-sensor signals (K channels); cp context → [B, S, H, K+2+C]."""
    idx = t_idx[:, None] + np.arange(h)[None, :]
    zw = zp[e_idx[:, None], idx]  # [B, H, S, K]
    cw = cp[e_idx[:, None], idx]  # [B, H, C]
    b, _, s, _ = zw.shape
    x = np.concatenate(
        [
            np.transpose(zw, (0, 2, 1, 3)),
            np.broadcast_to(typ[None, :, None, :], (b, s, h, typ.shape[1])),
            np.broadcast_to(cw[:, None], (b, s, h, cw.shape[-1])),
        ],
        -1,
    )
    return torch.from_numpy(np.ascontiguousarray(x, dtype=np.float32))


def pad(zz, ctx, h):
    """zz [E, T, S, K] (K signal channels)."""
    e = zz.shape[0]
    return (
        np.concatenate([np.zeros((e, h - 1, *zz.shape[2:]), np.float32), zz.astype(np.float32)], 1),
        np.concatenate([np.zeros((e, h - 1, ctx.shape[2]), np.float32), ctx.astype(np.float32)], 1),
    )


def type_matrix():
    typ = np.zeros((len(SENSORS), 2), np.float32)
    for i, t in enumerate(TYPES):
        typ[i, 0 if t == "pressure" else 1] = 1
    return typ


@torch.no_grad()
def predict_set(model, zz, ctx, valid, h, bs=8192, sensor_drop: list[int] | None = None) -> np.ndarray:
    model.eval()
    zp, cp = pad(zz, ctx, h)
    typ = type_matrix()
    e_idx, t_idx = np.nonzero(valid)
    p = np.zeros(valid.shape, np.float32)
    keep = [i for i in range(len(SENSORS)) if not sensor_drop or i not in sensor_drop]
    for i in range(0, len(e_idx), bs):
        x = gather(zp, cp, typ, e_idx[i : i + bs], t_idx[i : i + bs], h)[:, keep]
        m = torch.ones(x.shape[0], x.shape[1], dtype=torch.bool)
        logit, _ = model(x, m)
        p[e_idx[i : i + bs], t_idx[i : i + bs]] = torch.sigmoid(logit).numpy()
    return p


def train_set(zz, ctx, valid, y, h, epochs, seed, log) -> SensorSetNet:
    torch.manual_seed(seed)
    rng = np.random.Generator(np.random.PCG64(seed))
    model = SensorSetNet(hidden=32, history=h, n_signal=zz.shape[-1])
    opt = torch.optim.AdamW(model.parameters(), 2e-3, weight_decay=1e-4)
    zp, cp = pad(zz, ctx, h)
    typ = type_matrix()
    e_idx, t_idx = np.nonzero(valid)
    lab = y[e_idx, t_idx]
    pos, neg = np.flatnonzero(lab == 1), np.flatnonzero(lab == 0)
    n_per = 60000
    for ep_ in range(epochs):
        model.train()
        sel = np.concatenate([rng.choice(pos, n_per), rng.choice(neg, n_per)])
        rng.shuffle(sel)
        tot = 0.0
        for i in range(0, len(sel), 512):
            s = sel[i : i + 512]
            x = gather(zp, cp, typ, e_idx[s], t_idx[s], h)
            # sensor dropout: random subsets so the set model never relies on a fixed layout
            m = torch.from_numpy(rng.random((len(s), len(SENSORS))) > 0.2)
            m[~m.any(1), 4] = True
            logit, _ = model(x, m)
            loss = torch.nn.functional.binary_cross_entropy_with_logits(logit, torch.from_numpy(lab[s]))
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += loss.item() * len(s)
        log(f"[R3] epoch {ep_ + 1}/{epochs} loss {tot / len(sel):.4f}")
    return model


def summarise(name, params, m):
    return {
        "model": name,
        **params,
        "recall_MLB": m["recall_medium_large_burst"],
        **{f"far_{s}": m["far_by_type"].get(s) for s in OPERATIONAL},
        **{f"recall_{k}": v for k, v in m["recall_by_type"].items()},
        "delay_MEDIUM": m["median_delay_steps_by_type"].get("MEDIUM_LEAK"),
        "feasible": _rank_key(m)[0],
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--predictor", default="gnn_ds1_202610090559")
    p.add_argument("--features", default="data/features/ds1")
    p.add_argument("--processed", default="data/processed/ds1")
    p.add_argument("--history", type=int, default=24)
    p.add_argument("--epochs", type=int, default=12)
    p.add_argument("--seed", type=int, default=20261009)
    p.add_argument("--out", default="")
    p.add_argument(
        "--raw-channel", action="store_true", help="R3 also sees each sensor's type-normalised raw reading"
    )
    p.add_argument("--only-r3", action="store_true")
    args = p.parse_args(argv)
    torch.set_num_threads(10)
    out = Path(args.out or f"data/experiments/detsel_{datetime.now(UTC):%Y%m%d%H%M}")
    out.mkdir(parents=True, exist_ok=True)
    logf = open(out / "log.txt", "w")

    def log(msg):
        print(msg, flush=True)
        logf.write(msg + "\n")

    feat, proc = Path(args.features), Path(args.processed)
    scalers = json.loads((feat / "scalers.json").read_text())
    data = {s: load_split(feat, s) for s in ("train", "val")}  # test is never read
    res = {s: np.load(feat / "residuals" / f"{args.predictor}_{s}.npy").astype(np.float64) for s in data}
    rows = []

    # ---- R1: RTCA, σ in pump-flow bins from val-normal (as tune.py)
    v = data["val"]
    pump = v["ctx"][:, 3].astype(np.float64)
    table = estimate_binned_sigmas(res["val"][v["train_ok"]], pump[v["train_ok"]])
    zz_v, valid_v, lab_v = ep(v, res["val"] / sigma_matrix(pump, table))
    best = None
    r1_grid = (
        []
        if args.only_r3
        else list(itertools.product(SENSOR_SETS.items(), itertools.product(*GRID.values())))
    )
    for (sn, det), (k1, k2, w, t) in r1_grid:
        m, _ = evaluate_config(zz_v, valid_v, lab_v, k1, k2, w, t, det)
        if best is None or (*_rank_key(m), len(det)) > (*_rank_key(best[1]), len(best[0]["sensors"])):
            best = ({"sensors": sn, "k1": k1, "k2": k2, "W": w, "T": t}, m)
    if best:
        rows.append(summarise("R1_rtca", best[0], best[1]))
        log(f"[R1] {rows[-1]}")

    # ---- shared z for learned models: pooled σ from TRAIN normal
    sig = res["train"][data["train"]["train_ok"]].std(0)
    nodes = json.loads((feat / "graph.json").read_text())["node_order"]
    sens_cols = [nodes.index(n) for n in ("2", "4", "6")]
    ep_data = {}
    for s in data:
        zz, valid, lab = ep(data[s], res[s] / sig)
        if args.raw_channel:
            raw = np.concatenate(
                [
                    (data[s]["p_obs"][:, sens_cols] - scalers["pressure_m"]["mean"])
                    / scalers["pressure_m"]["std"],
                    (data[s]["q_obs"] - scalers["flow_lps"]["mean"]) / scalers["flow_lps"]["std"],
                ],
                1,
            ).astype(np.float64)
            rr, _, _ = ep(data[s], raw)
            zz = np.stack([zz, rr], -1)
        else:
            zz = zz[..., None]
        cx, _, _ = ep(data[s], context_features(data[s]["ctx"].astype(np.float64), scalers))
        y = labels_for(s, proc, lab, zz.shape[1])
        ep_data[s] = (zz, cx, valid, lab, y)

    # ---- R2: HistGradientBoosting on window features (fixed layout reference)
    from sklearn.ensemble import HistGradientBoostingClassifier

    t0 = time.time()
    zz, cx, valid, lab, y = ep_data["train"]
    if args.only_r3:
        f_tr = None
    else:
        f_tr = window_feats(zz[..., 0], cx)[valid]
    if f_tr is not None:
        y_tr = y[valid]
        rng = np.random.Generator(np.random.PCG64(args.seed))
        sub = rng.choice(len(y_tr), min(200000, len(y_tr)), replace=False)
        gbm = HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.08, max_leaf_nodes=31, random_state=0
        )
        gbm.fit(f_tr[sub], y_tr[sub])
        zz, cx, valid, lab, y = ep_data["val"]
        pv = np.zeros(valid.shape, np.float32)
        pv[valid] = gbm.predict_proba(window_feats(zz[..., 0], cx)[valid])[:, 1]
        params, m = tune_prob(pv, valid, lab)
        rows.append(summarise("R2_gbm_fixed_layout", params, m))
        log(f"[R2] {rows[-1]} ({time.time() - t0:.0f}s)")

    # ---- R3: SensorSetNet (generalised)
    t0 = time.time()
    zz, cx, valid, lab, y = ep_data["train"]
    model = train_set(zz, cx, valid, y, args.history, args.epochs, args.seed, log)
    zz, cx, valid, lab, y = ep_data["val"]
    pv = predict_set(model, zz, cx, valid, args.history)
    params, m = tune_prob(pv, valid, lab)
    r3name = "R3b_sensorset_resid+raw" if args.raw_channel else "R3_sensorset_generalised"
    rows.append(summarise(r3name, params, m))
    log(f"[R3] {rows[-1]} ({time.time() - t0:.0f}s)")
    # robustness: same model with a sensor removed (layout change without retraining)
    for drop in ([1], [2], [0, 1, 2]):
        pd_ = predict_set(model, zz, cx, valid, args.history, sensor_drop=drop)
        prm, mm = tune_prob(pd_, valid, lab)
        rows.append(summarise(f"{r3name}_drop_{'+'.join(SENSORS[i] for i in drop)}", prm, mm))
        log(f"[R3-drop] {rows[-1]}")
    torch.save(model.state_dict(), out / "sensorset_candidate.pt")

    df = pd.DataFrame(rows)
    df.to_csv(out / "selection_val.csv", index=False)
    log("\n" + df.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
