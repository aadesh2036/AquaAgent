"""Writer/merge go through fsspec, so the s3:// path is the same code as local; `memory://` stands in for S3."""

from __future__ import annotations

import fsspec
import pandas as pd
import pytest

from sim.generate import writer
from sim.generate.merge import merge
from sim.generate.runner import run_shard

CONFIG = "config/generation/ds1.yaml"


def test_write_read_roundtrip_and_schema(tmp_path):
    df = pd.DataFrame({"simulation_id": ["a", "a"], "sim_time_s": [0, 300], "sensor_id": ["S1", "S1"], "source_kind": ["node"] * 2,
                       "source_id": ["2"] * 2, "measurement": ["pressure_m"] * 2, "true_value": [1.0, 2.0],
                       "measured_value": [1.1, float("nan")], "sensor_fault_kind": [None, None]})  # fmt: skip
    uri = writer.write_table(df, "sensors", str(tmp_path / "x" / "part-000.parquet"))
    back = writer.read_table(uri)
    assert back["measured_value"].isna().tolist() == [False, True]  # missing = null
    import pyarrow.parquet as pq

    assert pq.read_schema(uri).metadata is None  # no pandas / writer metadata
    with pytest.raises(ValueError):
        writer.write_table(df.rename(columns={"true_value": "oops"}), "sensors", str(tmp_path / "y.parquet"))


def test_generate_and_merge_via_uri_scheme():
    fs = fsspec.filesystem("memory")
    root = "memory://aqua-test/ds"
    try:
        stats = run_shard(CONFIG, 0, 1, f"{root}/raw/shard=0/", limit=3)
        assert stats["n_valid"] == 3
        m = merge(CONFIG, f"{root}/raw", f"{root}/processed")
        assert m.n_valid == 3 and fs.exists("/aqua-test/ds/processed/manifest.json")
        assert fs.exists("/aqua-test/ds/processed/graph/part-000.parquet")
    finally:
        fs.rm("/aqua-test", recursive=True)
