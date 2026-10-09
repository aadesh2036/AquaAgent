"""Training script — runs IDENTICALLY locally and in SageMaker script mode (BACKBONE §9.1, §3.2).

Reads SM_CHANNEL_TRAIN / SM_CHANNEL_VAL / SM_MODEL_DIR / SM_OUTPUT_DATA_DIR with local defaults.
Dependencies: torch + numpy only (the SageMaker PyTorch container needs no extra wheels).

* Rows: ``train_ok`` rows of the train split only (operational sims + pre-fault steps, §9.1).
* Masks: fresh placement per sample per step (``ml.predictor.masking``); held-out placements are
  never sampled.
* Loss: MSE on standardised head at **unobserved scored nodes only** + ``flow_loss_weight`` × MSE on
  unobserved flow sensors. Observed inputs never contribute to the loss.
* Model selection: best val hidden-junction MAE (m) on a fixed, seeded val mask set (normal rows).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import torch

from ml.features.tensorize import GraphStatic, tensorize
from ml.predictor.masking import parse_placements, sample_masks

ARRAY_KEYS = ("p_obs", "p_obs_lag1", "p_obs_lag3", "q_obs", "ctx", "p_true", "q_true")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--arch", default="gnn", choices=["mlp", "gnn"])
    p.add_argument("--epochs", type=int, default=40)
    p.add_argument("--lr", type=float, default=2e-3)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--batch-size", type=int, default=512)
    p.add_argument("--hidden", type=int, default=0, help="0 = arch default (gnn 64, mlp 256)")
    p.add_argument("--layers", type=int, default=0, help="0 = arch default (gnn 4, mlp 3)")
    p.add_argument("--heads", type=int, default=4)
    p.add_argument("--dropout", type=float, default=0.0)
    p.add_argument("--p-default", type=float, default=0.5, help="share of samples on the contract layout")
    p.add_argument("--k-min", type=int, default=1)
    p.add_argument("--k-max", type=int, default=5)
    p.add_argument("--holdout-placements", default="3-5-7,2-5-7")
    p.add_argument("--flow-loss-weight", type=float, default=0.5)
    p.add_argument("--patience", type=int, default=10)
    p.add_argument("--max-train-rows", type=int, default=0, help="debug: subsample train rows")
    p.add_argument("--seed", type=int, default=20261008)
    p.add_argument("--dataset-version", default="ds1")
    p.add_argument("--model-version", default="")
    p.add_argument("--git-sha", default=os.environ.get("AQUA_GIT_SHA", "unknown"))
    p.add_argument("--threads", type=int, default=0)
    p.add_argument("--train", default=os.environ.get("SM_CHANNEL_TRAIN", "data/features/ds1"))
    p.add_argument("--val", default=os.environ.get("SM_CHANNEL_VAL", "data/features/ds1"))
    p.add_argument("--model-dir", default=os.environ.get("SM_MODEL_DIR", ""))
    p.add_argument("--output-dir", default=os.environ.get("SM_OUTPUT_DATA_DIR", ""))
    return p.parse_args(argv)


def load_split(path: str | Path, split: str) -> dict[str, np.ndarray]:
    with np.load(Path(path) / f"{split}.npz", allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def to_tensors(a: dict[str, np.ndarray], rows: np.ndarray) -> dict[str, torch.Tensor]:
    return {k: torch.from_numpy(np.ascontiguousarray(a[k][rows])) for k in ARRAY_KEYS}


def take(t: dict[str, torch.Tensor], idx: torch.Tensor) -> dict[str, torch.Tensor]:
    return {k: v[idx] for k, v in t.items()}


def build_model(cfg: dict, gs: GraphStatic) -> torch.nn.Module:
    if cfg["arch"] == "gnn":
        from ml.predictor.gnn import GNNPredictor

        return GNNPredictor(
            hidden=cfg["hidden"], layers=cfg["layers"], heads=cfg["heads"], dropout=cfg["dropout"]
        )
    from ml.predictor.mlp import MLPPredictor

    return MLPPredictor(gs, hidden=cfg["hidden"], layers=cfg["layers"], dropout=cfg["dropout"])


def masked_loss(model, batch, p_mask, q_mask, gs, flow_w):
    x, e = tensorize(batch, p_mask, q_mask, gs)
    head_z, flow_z = model(x, e, gs)
    tgt = gs.pressure_to_head_z(batch["p_true"])
    hid = (~p_mask) & gs.scored
    lp = ((head_z - tgt) ** 2 * hid).sum() / hid.sum().clamp_min(1)
    qh = ~q_mask
    lq = ((flow_z - gs.flow_to_z(batch["q_true"])) ** 2 * qh).sum() / qh.sum().clamp_min(1)
    return lp + flow_w * lq, head_z, flow_z


@torch.no_grad()
def evaluate(model, data, p_mask, q_mask, gs, bs=4096) -> dict:
    model.eval()
    junction = gs.node_static[:, 2].bool()
    ae_sum = se_sum = n_j = 0.0
    fae = fn = 0.0
    for i in range(0, len(p_mask), bs):
        sl = slice(i, i + bs)
        b = {k: v[sl] for k, v in data.items()}
        x, e = tensorize(b, p_mask[sl], q_mask[sl], gs)
        head_z, flow_z = model(x, e, gs)
        err = gs.head_z_to_pressure(head_z) - b["p_true"]
        hj = (~p_mask[sl]) & junction
        ae_sum += float((err.abs() * hj).sum())
        se_sum += float((err**2 * hj).sum())
        n_j += float(hj.sum())
        qh = ~q_mask[sl]
        fae += float(((gs.z_to_flow(flow_z) - b["q_true"]).abs() * qh).sum())
        fn += float(qh.sum())
    return {
        "hidden_junction_mae_m": ae_sum / max(n_j, 1),
        "hidden_junction_rmse_m": math.sqrt(se_sum / max(n_j, 1)),
        "masked_flow_mae_lps": fae / max(fn, 1),
    }


def main(argv: list[str] | None = None) -> int:
    """Train on NORMAL-only samples with random sensor masking (§9.1); write model + scalers + metrics."""
    args = parse_args(argv)
    torch.manual_seed(args.seed)
    if args.threads:
        torch.set_num_threads(args.threads)
    hidden = args.hidden or (64 if args.arch == "gnn" else 256)
    layers = args.layers or (4 if args.arch == "gnn" else 3)
    mv = args.model_version or f"{args.arch}_{args.dataset_version}_{datetime.now(UTC):%Y%m%d%H%M}"
    model_dir = Path(args.model_dir or f"data/models/predictor/{mv}")
    out_dir = Path(args.output_dir or f"data/experiments/{mv}")
    model_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    graph = json.loads((Path(args.train) / "graph.json").read_text())
    scalers = json.loads((Path(args.train) / "scalers.json").read_text())
    gs = GraphStatic.from_json(graph, scalers)
    holdout = parse_placements(args.holdout_placements, gs)

    tr_np, va_np = load_split(args.train, "train"), load_split(args.val, "val")
    rng = np.random.Generator(np.random.PCG64(args.seed))
    tr_rows = np.flatnonzero(tr_np["train_ok"])
    if args.max_train_rows:
        tr_rows = np.sort(rng.choice(tr_rows, args.max_train_rows, replace=False))
    va_rows = np.flatnonzero(va_np["train_ok"])
    assert not tr_np["post_fault"][tr_rows].any(), "post-fault row in training set (§9.1)"
    train, val = to_tensors(tr_np, tr_rows), to_tensors(va_np, va_rows)

    g_val = torch.Generator().manual_seed(args.seed + 1)
    vp, vq = sample_masks(len(va_rows), gs, g_val, args.p_default, (args.k_min, args.k_max), holdout)

    cfg = {
        "arch": args.arch,
        "hidden": hidden,
        "layers": layers,
        "heads": args.heads,
        "dropout": args.dropout,
    }
    model = build_model(cfg, gs)
    n_params = sum(p.numel() for p in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    steps_per_epoch = math.ceil(len(tr_rows) / args.batch_size)
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=args.lr, total_steps=args.epochs * steps_per_epoch, pct_start=0.1
    )
    g = torch.Generator().manual_seed(args.seed)
    print(
        f"[train] {mv} arch={args.arch} params={n_params} train_rows={len(tr_rows)} val_rows={len(va_rows)}"
    )

    best, best_epoch, curves, stale = math.inf, -1, [], 0
    t0 = time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        perm = torch.randperm(len(tr_rows), generator=g)
        tot = 0.0
        for i in range(steps_per_epoch):
            idx = perm[i * args.batch_size : (i + 1) * args.batch_size]
            pm, qm = sample_masks(len(idx), gs, g, args.p_default, (args.k_min, args.k_max), holdout)
            loss, _, _ = masked_loss(model, take(train, idx), pm, qm, gs, args.flow_loss_weight)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            tot += loss.item() * len(idx)
        vm = evaluate(model, val, vp, vq, gs)
        row = {
            "epoch": epoch,
            "train_loss": tot / len(tr_rows),
            **vm,
            "lr": sched.get_last_lr()[0],
            "elapsed_s": round(time.time() - t0, 1),
        }
        curves.append(row)
        print("[epoch] " + json.dumps(row), flush=True)
        if vm["hidden_junction_mae_m"] < best - 1e-5:
            best, best_epoch, stale = vm["hidden_junction_mae_m"], epoch, 0
            torch.save(model.state_dict(), model_dir / "model.pt")
        else:
            stale += 1
            if stale >= args.patience:
                print(f"[train] early stop at epoch {epoch}")
                break

    model.load_state_dict(torch.load(model_dir / "model.pt", weights_only=True))
    final = evaluate(model, val, vp, vq, gs)
    meta = {
        "model_version": mv,
        "arch": args.arch,
        "model_config": cfg,
        "n_params": n_params,
        "dataset_version": args.dataset_version,
        "dataset_git_sha": graph.get("dataset_git_sha"),
        "code_git_sha": args.git_sha,
        "network_id": graph["network_id"],
        "sensor_layout_id": graph["sensor_layout_id"],
        "node_order": graph["node_order"],
        "node_features": graph["node_features"],
        "edge_features": graph["edge_features"],
        "target": "standardised hydraulic head at scored nodes (pressure = head - elevation); F1/F2 flow",
        "training": {
            **{k: v for k, v in vars(args).items() if k not in ("train", "val", "model_dir", "output_dir")},
            "optimizer": "AdamW",
            "schedule": "OneCycle",
            "loss": "masked MSE (hidden scored nodes) + w*MSE (masked flows)",
            "train_rows": int(len(tr_rows)),
            "val_rows": int(len(va_rows)),
            "train_sim_ids": [str(s) for s in tr_np["sim_ids"]],
            "val_sim_ids": [str(s) for s in va_np["sim_ids"]],
            "best_epoch": best_epoch,
            "epochs_run": len(curves),
            "train_time_s": round(time.time() - t0, 1),
        },
        "val_metrics_selection_masks": final,
    }
    (model_dir / "meta.json").write_text(json.dumps(meta, indent=1))
    shutil.copy(Path(args.train) / "scalers.json", model_dir / "scalers.json")
    shutil.copy(Path(args.train) / "graph.json", model_dir / "graph.json")
    with open(out_dir / "curves.csv", "w") as f:
        f.write(",".join(curves[0]) + "\n")
        for r in curves:
            f.write(",".join(str(v) for v in r.values()) + "\n")
    (out_dir / "train_metrics.json").write_text(json.dumps({"model_version": mv, **final}, indent=1))
    print(f"[done] {mv} best_epoch={best_epoch} val={json.dumps(final)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
