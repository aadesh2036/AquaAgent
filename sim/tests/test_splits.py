"""Split integrity (module 02 §6 step 6, BACKBONE §8.5)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from shared.contracts.models import TABLE_COLUMNS, DatasetManifest
from sim.generate.merge import assign_splits, holdout_mask
from sim.scenarios.sampler import plan_dataset

CFG = yaml.safe_load((Path(__file__).resolve().parents[2] / "config/generation/ds1.yaml").read_text())
HOLDOUT = CFG["holdout_test_only"]


@pytest.fixture(scope="module")
def frame():
    rows = []
    for s in plan_dataset(CFG):
        f = s.faults[0] if s.faults else None
        rows.append(
            {
                "simulation_id": s.simulation_id,
                "scenario_type": s.scenario_type.value,
                "fault_type": f.fault_type.value if f else None,
                "location_kind": f.location_kind.value if f else None,
                "location_id": f.location_id if f else None,
            }
        )
    return pd.DataFrame(rows)


def test_full_plan_split_integrity(frame):
    split = assign_splits(frame, CFG["dataset_seed"], HOLDOUT)
    assert split.index.equals(frame.index) and set(split) == {"train", "val", "test"}
    assert frame["simulation_id"].is_unique  # => no sim in two splits
    # deterministic
    assert split.equals(assign_splits(frame, CFG["dataset_seed"], HOLDOUT))
    assert not split.equals(assign_splits(frame, CFG["dataset_seed"] + 1, HOLDOUT))
    for t, grp in frame.groupby("scenario_type"):
        n = len(grp)
        if n < 100:
            continue
        frac = split.loc[grp.index].value_counts(normalize=True)
        for s, want in (("train", 0.70), ("val", 0.15), ("test", 0.15)):
            assert abs(frac.get(s, 0.0) - want) <= 0.03, (t, s, frac.to_dict())


def test_holdout_only_in_test(frame):
    split = assign_splits(frame, CFG["dataset_seed"], HOLDOUT)
    held = holdout_mask(frame, HOLDOUT)
    assert held.sum() > 50
    assert set(split[held]) == {"test"}
    assert not (held & (split != "test")).any()
    # held-out locations never appear among leak sims of train/val
    leaks = frame["fault_type"].isin(["LEAK", "BURST"])
    loc = frame["location_kind"].astype(str) + ":" + frame["location_id"].astype(str)
    assert not (leaks & loc.isin(HOLDOUT) & split.isin(["train", "val"])).any()


def test_merged_dataset_layout(smoke_dataset):
    raw, out, manifest = smoke_dataset
    out = Path(out)
    m = DatasetManifest.model_validate(json.loads((out / "manifest.json").read_text()))
    assert m == manifest and m.n_requested == 16 and m.n_valid + m.n_failed == 16
    assert sum(m.counts_by_split.values()) == m.n_valid == sum(m.counts_by_scenario_type.values())
    assert m.holdout.fault_locations_test_only == HOLDOUT and m.wntr_version == "1.5.0"
    seen = {}
    for s in ("train", "val", "test"):
        for t in ("scenarios", "node_states", "link_states", "tank_states", "pump_states", "sensors", "context"):
            df = pd.read_parquet(out / f"split={s}" / t / "part-000.parquet")
            assert list(df.columns) == list(TABLE_COLUMNS[t])
            for sid in df["simulation_id"].unique():
                assert seen.setdefault(sid, s) == s  # a sim lives in exactly one split
    assert (out / "graph" / "part-000.parquet").exists() and (out / "validation_log" / "part-000.parquet").exists()
    graph = pd.read_parquet(out / "graph" / "part-000.parquet")
    assert list(graph.columns) == list(TABLE_COLUMNS["graph"]) and len(graph) == 8 + 9
