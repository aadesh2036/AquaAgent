"""Predictor evaluation sweep (BACKBONE §9.1, §9.5, §16) — baseline vs trained artifacts.

For every model, on the normal rows (operational sims + pre-fault steps) of one split:

* **coverage** — every placement of k = 1..5 pressure sensors over the 6 junctions (all C(6,k), so
  no placement cherry-picking), F1/F2 present. Error at hidden junctions (tank excluded: its pressure
  equals the SCADA tank level, so scoring it would flatter every model).
* **hop** — the same errors grouped by pipe hops to the nearest pressure sensor.
* **placement generalisation** — held-out placements (never sampled in training) vs seen ones.
* **contract layout** — S1–S3 + F1/F2: hidden junctions 3/5/7 (§9.5 target < 1.0 m), 5-sensor
  leave-one-out, flows dropped ablation, per scenario type.
* **residual sanity (val only, G4 test 5)** — LOO z-scores (σ from val normal) on LARGE_LEAK sims.

Usage: python -m ml.predictor.evaluate --split val --models data/models/predictor/<mv> [...]
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from ml.evaluation.hop_error import hops_to_placement
from ml.evaluation.metrics import predictor_metrics
from ml.features.builder import SCENARIO_TYPES
from ml.features.tensorize import GraphStatic, tensorize
from ml.predictor.baseline import NearestSensorBaseline, pipe_hop_matrix
from ml.predictor.masking import all_placements, default_masks, parse_placements, placement_mask
from ml.predictor.predict import load_artifact
from ml.predictor.train import ARRAY_KEYS, load_split

SERIES_COLORS = {"baseline": "#2a78d6", "mlp": "#eb6834", "gnn": "#1baf7a"}  # validated, slots 1–3
SERIES_MARKERS = {"baseline": "o", "mlp": "s", "gnn": "^"}


class Runner:
    """Uniform interface: (batch, p_mask, q_mask) → (pressure_m [B,N], flow_lps [B,F] | None)."""

    def __init__(self, name: str, gs: GraphStatic, model=None, baseline=None) -> None:
        self.name, self.gs, self.model, self.baseline = name, gs, model, baseline

    @torch.no_grad()
    def __call__(self, b, pm, qm, bs: int = 8192):
        ps, qs = [], []
        for i in range(0, len(pm), bs):
            sl = slice(i, i + bs)
            bb = {k: v[sl] for k, v in b.items()}
            if self.baseline is not None:
                ps.append(self.baseline.predict_pressure(bb, pm[sl]))
                continue
            x, e = tensorize(bb, pm[sl], qm[sl], self.gs)
            hz, qz = self.model(x, e, self.gs)
            ps.append(self.gs.head_z_to_pressure(hz))
            qs.append(self.gs.z_to_flow(qz))
        return torch.cat(ps), (torch.cat(qs) if qs else None)


def _cells(name, pid, k, seen, err, true, hops, hidden, scen) -> pd.DataFrame:
    """Sufficient statistics per (node, scenario) for one model × placement."""
    rows = []
    n_nodes = err.shape[1]
    for j in range(n_nodes):
        if not hidden[j]:
            continue
        df = pd.DataFrame({"e": err[:, j], "t": true[:, j], "s": scen})
        g = df.groupby("s")
        agg = pd.DataFrame(
            {
                "n": g.size(),
                "sae": g.e.apply(lambda x: np.abs(x).sum()),
                "sse": g.e.apply(lambda x: (x**2).sum()),
                "st": g.t.sum(),
                "st2": g.t.apply(lambda x: (x**2).sum()),
                "sape": g.apply(
                    lambda d: (np.abs(d.e) / np.maximum(np.abs(d.t), 1e-6)).sum(), include_groups=False
                ),
            }
        ).reset_index()
        agg["model"], agg["placement"], agg["k"], agg["seen"], agg["node"], agg["hop"] = (
            name,
            pid,
            k,
            seen,
            j,
            int(hops[j]),
        )
        rows.append(agg)
    return pd.concat(rows, ignore_index=True)


def _summ(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    # macro R²: computed per (placement, node) cell, then averaged — avoids between-node variance inflation
    cell_keys = list(dict.fromkeys([*keys, "placement", "node"]))
    cell = df.groupby(cell_keys)[["n", "sse", "st", "st2"]].sum().reset_index()
    sst = cell.st2 - cell.st**2 / cell.n
    cell["r2"] = np.where(sst > 1e-9, 1 - cell.sse / sst, np.nan)
    g = df.groupby(keys)[["n", "sae", "sse", "sape"]].sum()
    out = pd.DataFrame(
        {
            "mae_m": g.sae / g.n,
            "rmse_m": np.sqrt(g.sse / g.n),
            "mape_pct": 100 * g.sape / g.n,
            "n": g.n,
            "r2_macro": cell.groupby(keys).r2.mean(),
        }
    )
    return out.reset_index()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--features", default="data/features/ds1")
    p.add_argument("--split", default="val", choices=["val", "test"])
    p.add_argument("--models", nargs="*", default=[])
    p.add_argument("--stride", type=int, default=2, help="evaluate every n-th normal row (time subsample)")
    p.add_argument("--out", default="")
    args = p.parse_args(argv)
    torch.set_num_threads(max(1, torch.get_num_threads()))

    feat = Path(args.features)
    graph = json.loads((feat / "graph.json").read_text())
    gs = GraphStatic.from_json(graph, json.loads((feat / "scalers.json").read_text()))
    a = load_split(feat, args.split)
    rows = np.flatnonzero(a["train_ok"])[:: args.stride]
    b = {k: torch.from_numpy(np.ascontiguousarray(a[k][rows])) for k in ARRAY_KEYS}
    scen = np.array(SCENARIO_TYPES)[a["scenario_code"][rows]]
    true = b["p_true"].numpy()
    junction = gs.node_static[:, 2].bool().numpy()
    hopm = torch.tensor(pipe_hop_matrix(graph), dtype=torch.float32)

    runners = [Runner("baseline", gs, baseline=NearestSensorBaseline(gs, graph))]
    holdout, metas = set(), {}
    for d in args.models:
        art = load_artifact(d)
        if art.gs.scalers != gs.scalers:
            raise SystemExit(f"{d}: scalers differ from {feat} — artifact built from other features")
        runners.append(Runner(art.meta["arch"], art.gs, model=art.model))
        metas[art.meta["arch"]] = art.meta
        holdout |= parse_placements(art.meta["training"]["holdout_placements"], gs)
    out = Path(args.out or f"data/experiments/eval_{args.split}_{datetime.now(UTC):%Y%m%d%H%M}")
    (out / "plots").mkdir(parents=True, exist_ok=True)
    n_rows = len(rows)
    print(
        f"[eval] split={args.split} normal_rows={n_rows} (stride {args.stride}) models={[r.name for r in runners]}"
    )

    # ---- coverage / hop / placement sweep
    cells = []
    q_all = torch.ones(n_rows, len(gs.flow_edge_fwd), dtype=torch.bool)
    for k in range(1, 6):
        for pl in all_placements(gs, k):
            pm = placement_mask(pl, n_rows, gs)
            hops = hops_to_placement(hopm, pm[:1])[0].numpy()
            hidden = junction & ~pm[0].numpy()
            pid = "-".join(gs.node_order[i] for i in sorted(pl))
            for r in runners:
                pred, _ = r(b, pm, q_all)
                cells.append(
                    _cells(r.name, pid, k, pl not in holdout, pred.numpy() - true, true, hops, hidden, scen)
                )
        print(f"[eval] k={k} done")
    cells = pd.concat(cells, ignore_index=True)
    cells.to_csv(out / "cells.csv.gz", index=False)
    coverage = _summ(cells, ["model", "k"])
    coverage["coverage_pct"] = 100 * coverage.k / int(junction.sum())
    hop = _summ(cells, ["model", "hop"])
    hop_k = _summ(cells, ["model", "k", "hop"])
    by_pl = _summ(cells, ["model", "k", "placement", "seen"])
    coverage.to_csv(out / "coverage.csv", index=False)
    hop.to_csv(out / "hop_error.csv", index=False)
    hop_k.to_csv(out / "hop_error_by_k.csv", index=False)
    by_pl.to_csv(out / "placements.csv", index=False)
    k3 = by_pl[by_pl.k == 3]
    generalisation = {
        m: {
            "seen_k3_mae_m": float(g[g.seen].mae_m.mean()),
            "heldout_k3_mae_m": float(g[~g.seen].mae_m.mean()),
            "heldout": g[~g.seen][["placement", "mae_m"]].to_dict("records"),
        }
        for m, g in k3.groupby("model")
    }

    # ---- contract layout: hidden junctions, LOO, flow ablation, per scenario
    contract = {}
    scatter = {}
    for r in runners:
        pm, qm = default_masks(n_rows, gs)
        pred, _ = r(b, pm, qm)
        hid = np.broadcast_to(junction & ~pm[0].numpy(), true.shape)
        res = {"hidden_junctions": predictor_metrics(true, pred.numpy(), hid)}
        res["per_node_mae_m"] = {
            gs.node_order[j]: float(np.abs(pred[:, j].numpy() - true[:, j]).mean())
            for j in np.flatnonzero(hid[0])
        }
        res["per_scenario_mae_m"] = {
            s: float(np.abs(pred.numpy() - true)[(scen == s)][:, hid[0]].mean()) for s in sorted(set(scen))
        }
        scatter[r.name] = (true[:, hid[0]].ravel(), pred.numpy()[:, hid[0]].ravel())
        _, qm0 = default_masks(n_rows, gs, drop="F1")
        qm0[:] = False
        pred_nf, _ = r(b, pm, qm0)
        res["no_flow_sensors_hidden_junctions"] = predictor_metrics(true, pred_nf.numpy(), hid)
        loo = {}
        for i, sid in enumerate(("S1", "S2", "S3")):
            pmd, qmd = default_masks(n_rows, gs, drop=sid)
            pd_, _ = r(b, pmd, qmd)
            j = gs.default_sensor_idx[i]
            loo[sid] = predictor_metrics(true[:, j], pd_[:, j].numpy(), np.ones(n_rows, bool))
        res["loo_pressure_vs_true"] = loo
        if r.model is not None:
            lf = {}
            for f, fid in enumerate(("F1", "F2")):
                pmd, qmd = default_masks(n_rows, gs, drop=fid)
                _, qd = r(b, pmd, qmd)
                lf[fid] = {"mae_lps": float((qd[:, f] - b["q_true"][:, f]).abs().mean())}
            res["loo_flow_vs_true"] = lf
        contract[r.name] = res

    # ---- residual sanity on val (G4 test 5): LOO residual z on LARGE_LEAK post-fault
    sanity = {}
    if args.split == "val":
        sanity = residual_sanity(a, runners, gs)

    metrics = {
        "split": args.split,
        "normal_rows_evaluated": n_rows,
        "stride": args.stride,
        "n_sims": int(len(np.unique(a["sim_code"][rows]))),
        "scored": "hidden junctions only (tank excluded: pressure == SCADA tank level)",
        "hop_definition": "pipe hops to nearest pressure sensor of the placement (pump excluded)",
        "holdout_placements": sorted("-".join(gs.node_order[i] for i in sorted(h)) for h in holdout),
        "models": {
            m: {
                "model_version": metas[m]["model_version"],
                "n_params": metas[m]["n_params"],
                "best_epoch": metas[m]["training"]["best_epoch"],
            }
            for m in metas
        },
        "contract_layout": contract,
        "coverage": coverage.to_dict("records"),
        "hop": hop.to_dict("records"),
        "placement_generalisation": generalisation,
        "residual_sanity": sanity,
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=1, default=float))
    plots(out, coverage, hop_k, scatter)
    print(coverage.pivot(index="k", columns="model", values="mae_m").round(3).to_string())
    print(hop.pivot(index="hop", columns="model", values="mae_m").round(3).to_string())
    print(json.dumps({m: c["hidden_junctions"] for m, c in contract.items()}, indent=1))
    print(json.dumps(generalisation, indent=1, default=float)[:1500])
    if sanity:
        print(json.dumps(sanity, indent=1))
    print(f"[eval] wrote {out}")
    return 0


def residual_sanity(a, runners, gs) -> dict:
    """σ_s from val-normal LOO residuals; fraction of LARGE_LEAK sims with max post-fault |z| > 3."""
    sc = np.array(SCENARIO_TYPES)[a["scenario_code"]]
    normal = np.flatnonzero(a["train_ok"])
    leak = np.flatnonzero((sc == "LARGE_LEAK") & a["post_fault"])
    out = {}
    for r in runners:

        def loo_resid(rows, r=r):
            b = {k: torch.from_numpy(np.ascontiguousarray(a[k][rows])) for k in ARRAY_KEYS}
            res = {}
            for i, sid in enumerate(("S1", "S2", "S3")):
                pm, qm = default_masks(len(rows), gs, drop=sid)
                p, _ = r(b, pm, qm)
                j = gs.default_sensor_idx[i]
                res[sid] = (b["p_obs"][:, j] - p[:, j]).numpy()
            if r.model is not None:
                for f, fid in enumerate(("F1", "F2")):
                    pm, qm = default_masks(len(rows), gs, drop=fid)
                    _, q = r(b, pm, qm)
                    res[fid] = (b["q_obs"][:, f] - q[:, f]).numpy()
            return res

        rn, rl = loo_resid(normal), loo_resid(leak)
        sig = {s: float(np.std(v)) for s, v in rn.items()}
        z = np.max(np.stack([np.abs(rl[s]) / sig[s] for s in rl]), axis=0)
        zn = np.max(np.stack([np.abs(rn[s]) / sig[s] for s in rn]), axis=0)
        sims = a["sim_code"][leak]
        per_sim = pd.Series(z).groupby(sims).max()
        per_sim_n = pd.Series(zn).groupby(a["sim_code"][normal]).max()
        out[r.name] = {
            "sigma_val_normal": sig,
            "large_leak_sims": int(len(per_sim)),
            "frac_large_leak_sims_max_z_gt_3": float((per_sim > 3).mean()),
            "frac_normal_rows_max_z_gt_3": float((zn > 3).mean()),
            "frac_normal_sims_max_z_gt_3": float((per_sim_n > 3).mean()),
        }
    return out


def plots(out: Path, coverage: pd.DataFrame, hop_k: pd.DataFrame, scatter: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": "#e6e5e0",
            "grid.linewidth": 0.6,
            "axes.edgecolor": "#8a8984",
            "axes.labelcolor": "#52514e",
            "xtick.color": "#52514e",
            "ytick.color": "#52514e",
            "figure.facecolor": "#fcfcfb",
            "axes.facecolor": "#fcfcfb",
            "font.size": 10,
        }
    )

    fig, ax = plt.subplots(figsize=(6.4, 4))
    for m, g in coverage.groupby("model"):
        g = g.sort_values("k")
        ax.plot(
            g.coverage_pct,
            g.mae_m,
            color=SERIES_COLORS.get(m),
            marker=SERIES_MARKERS.get(m),
            lw=2,
            ms=7,
            label=m,
        )
        ax.annotate(
            m,
            (g.coverage_pct.iloc[-1], g.mae_m.iloc[-1]),
            xytext=(8, {"mlp": 7, "gnn": -7}.get(m, 0)),  # learned models nearly coincide
            textcoords="offset points",
            va="center",
            color="#0b0b0b",
            fontsize=9,
        )
    ax.set(
        xlabel="Junctions instrumented with pressure sensors (%)  [k = 1..5 of 6, all placements]",
        ylabel="Hidden-junction MAE (m)",
        title="Sensor coverage vs reconstruction error (log scale)",
    )
    ax.set_yscale("log")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out / "plots/coverage_vs_mae.png", dpi=150)
    plt.close(fig)

    hk = hop_k.groupby(["model", "hop"]).apply(
        lambda g: (g.mae_m * g.n).sum() / g.n.sum(), include_groups=False
    )
    fig, ax = plt.subplots(figsize=(6.4, 4))
    for m in hk.index.get_level_values(0).unique():
        s = hk[m]
        ax.plot(
            s.index, s.values, color=SERIES_COLORS.get(m), marker=SERIES_MARKERS.get(m), lw=2, ms=7, label=m
        )
    ax.set(
        xlabel="Pipe hops to nearest pressure sensor",
        ylabel="Hidden-junction MAE (m)",
        title="Error vs graph distance (all placements, k = 1..5; log scale)",
    )
    ax.set_xticks(sorted(hk.index.get_level_values(1).unique()))
    ax.set_yscale("log")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out / "plots/hop_vs_mae.png", dpi=150)
    plt.close(fig)

    n = len(scatter)
    fig, axes = plt.subplots(1, n, figsize=(3.6 * n, 3.6), sharex=True, sharey=True)
    rng = np.random.Generator(np.random.PCG64(0))
    for ax, (m, (t, pr)) in zip(np.atleast_1d(axes), scatter.items(), strict=True):
        i = rng.choice(len(t), min(6000, len(t)), replace=False)
        ax.scatter(t[i], pr[i], s=3, alpha=0.35, color=SERIES_COLORS.get(m), linewidths=0)
        lo, hi = float(np.min(t)), float(np.max(t))
        ax.plot([lo, hi], [lo, hi], color="#8a8984", lw=1)
        ax.set(title=f"{m} — contract layout", xlabel="True pressure (m)")
    np.atleast_1d(axes)[0].set_ylabel("Predicted pressure (m)")
    fig.tight_layout()
    fig.savefig(out / "plots/pred_vs_true_default.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
