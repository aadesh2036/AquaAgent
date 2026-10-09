"""Leakage / firewall tests for the predictor (BACKBONE §11, G4; docs/modules/04 §8)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from ml.features import builder
from ml.features.tensorize import GraphStatic, tensorize
from ml.predictor.masking import default_masks, parse_placements, sample_masks
from shared.contracts.models import FORBIDDEN_INPUT_COLUMNS

FEAT = Path("data/features/ds1")
PROC = Path("data/processed/ds1")
needs_features = pytest.mark.skipif(not (FEAT / "train.npz").exists(), reason="run `make features` first")
needs_processed = pytest.mark.skipif(
    not (PROC / "manifest.json").exists(), reason="processed ds1 not present"
)


@pytest.fixture(scope="module")
def gs() -> GraphStatic:
    return GraphStatic.from_json(
        json.loads((FEAT / "graph.json").read_text()), json.loads((FEAT / "scalers.json").read_text())
    )


@pytest.fixture(scope="module")
def train() -> dict:
    with np.load(FEAT / "train.npz") as z:
        return {k: z[k] for k in z.files}


def test_input_reader_columns_are_not_forbidden() -> None:
    assert not set(builder.SENSOR_INPUT_COLUMNS) & FORBIDDEN_INPUT_COLUMNS
    assert not set(builder.CONTEXT_INPUT_COLUMNS) & FORBIDDEN_INPUT_COLUMNS


@needs_processed
def test_input_reader_only_touches_allowed_columns(monkeypatch) -> None:
    """_read_inputs must request explicit, allowed columns from sensors/context only."""
    seen: list[tuple[str, tuple]] = []
    real = pd.read_parquet

    def spy(path, columns=None, **kw):
        seen.append((Path(path).name, tuple(columns or ())))
        return real(path, columns=columns, **kw)

    monkeypatch.setattr(builder.pd, "read_parquet", spy)
    graph = builder.build_graph(PROC)  # reads the static `graph` table (an allowed input)
    seen.clear()
    builder._read_inputs(PROC / "split=val", graph)
    tables = {t for t, _ in seen}
    assert tables == {"sensors", "context"}
    for _, cols in seen:
        assert cols, "inputs must be read with an explicit column list"
        assert not set(cols) & FORBIDDEN_INPUT_COLUMNS


@needs_features
@needs_processed
def test_default_sensor_inputs_equal_recorded_measured_value(gs, train) -> None:
    s = pd.read_parquet(
        PROC / "split=train/sensors", columns=["simulation_id", "sim_time_s", "sensor_id", "measured_value"]
    )
    s = s[s.sensor_id == "S2"].sort_values(["simulation_id", "sim_time_s"])
    j = gs.node_order.index("4")
    np.testing.assert_allclose(train["p_obs"][:, j], s.measured_value.to_numpy(np.float32), rtol=0, atol=1e-6)


@needs_features
def test_unobserved_values_never_reach_features(gs, train) -> None:
    """Changing p_obs/lags/flows at uninstrumented locations leaves x and edge_attr bit-identical."""
    rows = np.arange(512)
    b = {k: torch.from_numpy(train[k][rows]) for k in ("p_obs", "p_obs_lag1", "p_obs_lag3", "q_obs", "ctx")}
    g = torch.Generator().manual_seed(0)
    pm, qm = sample_masks(len(rows), gs, g)
    x0, e0 = tensorize(b, pm, qm, gs)
    b2 = {k: v.clone() for k, v in b.items()}
    for key in ("p_obs", "p_obs_lag1", "p_obs_lag3"):
        b2[key][~pm] = 1e6
    b2["q_obs"][~qm] = -1e6
    x1, e1 = tensorize(b2, pm, qm, gs)
    assert torch.equal(x0, x1) and torch.equal(e0, e1)


@needs_features
def test_training_rows_are_normal_only_and_splits_disjoint(train) -> None:
    assert not (train["train_ok"] & train["post_fault"]).any()
    ids = {}
    for split in ("train", "val", "test"):
        with np.load(FEAT / f"{split}.npz") as z:
            ids[split] = set(z["sim_ids"].tolist())
    assert not ids["train"] & ids["val"] and not ids["train"] & ids["test"] and not ids["val"] & ids["test"]


@needs_features
def test_holdout_placements_never_sampled(gs) -> None:
    hold = parse_placements("3-5-7,2-5-7", gs)
    g = torch.Generator().manual_seed(1)
    pm, _ = sample_masks(20000, gs, g, p_default=0.0, holdout=hold)
    for h in hold:
        hm = torch.zeros(gs.n_nodes, dtype=torch.bool)
        hm[sorted(h)] = True
        assert not (pm == hm).all(1).any()
    assert set(pm.sum(1).unique().tolist()) == {1, 2, 3, 4, 5}


@needs_features
def test_default_layout_loo_masks(gs) -> None:
    for sid, n_p, n_q in (("S2", 2, 2), ("F1", 3, 1), (None, 3, 2)):
        pm, qm = default_masks(4, gs, drop=sid)
        assert int(pm[0].sum()) == n_p and int(qm[0].sum()) == n_q


@needs_features
def test_shuffled_targets_destroy_performance(gs, train) -> None:
    """G4: a model trained on shuffled hidden-node targets must be ≥ 3× worse on real targets."""
    from ml.predictor.mlp import MLPPredictor
    from ml.predictor.train import evaluate, masked_loss

    rng = np.random.Generator(np.random.PCG64(0))
    keys = ("p_obs", "p_obs_lag1", "p_obs_lag3", "q_obs", "ctx", "p_true", "q_true")
    ok = np.flatnonzero(train["train_ok"])
    tr = rng.choice(ok, 20000, replace=False)
    va = rng.choice(np.setdiff1d(ok, tr), 4000, replace=False)
    val = {k: torch.from_numpy(train[k][va]) for k in keys}
    vp, vq = sample_masks(len(va), gs, torch.Generator().manual_seed(2))

    def fit(shuffle: bool) -> float:
        torch.manual_seed(0)
        data = {k: torch.from_numpy(train[k][tr]) for k in keys}
        if shuffle:
            data["p_true"] = data["p_true"][torch.randperm(len(tr))]
        m = MLPPredictor(gs, hidden=128)
        opt = torch.optim.Adam(m.parameters(), 2e-3)
        g = torch.Generator().manual_seed(3)
        for _ in range(3):
            for idx in torch.randperm(len(tr), generator=g).split(512):
                pm, qm = sample_masks(len(idx), gs, g)
                loss, _, _ = masked_loss(m, {k: v[idx] for k, v in data.items()}, pm, qm, gs, 0.5)
                opt.zero_grad()
                loss.backward()
                opt.step()
        return evaluate(m, val, vp, vq, gs)["hidden_junction_mae_m"]

    real, shuffled = fit(False), fit(True)
    assert shuffled >= 3 * real, (real, shuffled)
