"""Firewall in data form (BACKBONE §11, module 02 §8)."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

from shared.contracts.models import FORBIDDEN_INPUT_COLUMNS, MODEL_INPUT_TABLES, TABLE_COLUMNS

HIDDEN_ID = re.compile(r"^LK_|_B$")
HIDDEN_NODES = {"3", "5", "7"}
ALL_TABLES = ("scenarios", "node_states", "link_states", "tank_states", "pump_states", "sensors", "context", "graph")


@pytest.fixture(scope="module")
def tables(smoke_dataset):
    _, out, _ = smoke_dataset
    out = Path(out)
    got = {}
    for t in ALL_TABLES:
        parts = [out / "graph" / "part-000.parquet"] if t == "graph" else sorted(out.glob(f"split=*/{t}/part-000.parquet"))
        got[t] = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
    return got


def test_model_inputs_have_no_forbidden_columns(tables):
    for t in ("sensors", "context"):
        bad = (set(tables[t].columns) & FORBIDDEN_INPUT_COLUMNS) - ({"true_value", "sensor_fault_kind"} if t == "sensors" else set())
        assert not bad, (t, bad)
    # the declared exceptions are exactly the documented ones
    assert set(tables["sensors"].columns) & FORBIDDEN_INPUT_COLUMNS == {"true_value", "sensor_fault_kind"}
    assert not set(tables["context"].columns) & FORBIDDEN_INPUT_COLUMNS
    assert not set(tables["graph"].columns) & FORBIDDEN_INPUT_COLUMNS
    assert MODEL_INPUT_TABLES == {"sensors", "context", "graph"}
    assert list(tables["context"].columns) == list(TABLE_COLUMNS["context"])


def test_no_hidden_ids_outside_spec_json(tables):
    for name, df in tables.items():
        for col in df.columns:
            if name == "scenarios" and col == "spec_json":
                continue
            if df[col].dtype == object:
                vals = df[col].dropna().astype(str)
                assert not vals.str.contains(HIDDEN_ID).any(), (name, col)
    # graph features must not leak either
    assert not tables["graph"]["features_json"].str.contains("LK_").any()


def test_hidden_nodes_never_in_sensors(tables):
    s = tables["sensors"]
    assert HIDDEN_NODES.isdisjoint(set(s.loc[s["source_kind"] == "node", "source_id"]))
    assert set(s.loc[s["source_kind"] == "node", "source_id"]) == {"2", "4", "6"}
    assert set(s.loc[s["source_kind"] == "link", "source_id"]) == {"3", "6"}


def test_measured_differs_from_true_where_sigma_positive(tables):
    s = tables["sensors"]
    assert (s["measured_value"] != s["true_value"]).mean() > 0.99
    assert s["measured_value"].notna().all() and s["sensor_fault_kind"].isna().all()
    # ground truth is only in the state tables / scenarios
    assert {"scenarios", "node_states", "link_states"}.isdisjoint(MODEL_INPUT_TABLES)
