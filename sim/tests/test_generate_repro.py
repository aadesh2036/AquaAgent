"""G2 reproducibility: `generate --limit 20` twice -> identical Parquet SHA-256 (module 02 §6 step 5).

WNTR's C++ evaluator orders its Jacobian by pointer, so raw results jitter ~1e-13 between runs;
`runner.quantize` rounds to a fixed physical resolution, which makes the files byte-identical.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from sim.cli import main

CONFIG = "config/generation/ds1.yaml"


def _hashes(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*.parquet"))}


def test_generate_twice_identical_parquet(tmp_path):
    outs = []
    for k in range(2):
        out = tmp_path / f"run{k}" / "shard=0"
        rc = main(["generate", "--config", CONFIG, "--shard", "0", "--num-shards", "1", "--limit", "20", "--out", str(out)])
        assert rc == 0
        outs.append(out)
    a, b = _hashes(outs[0]), _hashes(outs[1])
    assert set(a) == {f"{t}/part-000.parquet" for t in (
        "scenarios", "node_states", "link_states", "tank_states", "pump_states", "sensors", "context", "validation_log")}  # fmt: skip
    assert a == b


def test_shards_partition_the_plan(tmp_path):
    for sh in range(2):
        assert main(["generate", "--config", CONFIG, "--shard", str(sh), "--num-shards", "2", "--limit", "3", "--out", str(tmp_path / f"s{sh}")]) == 0
    import pandas as pd

    ids = [set(pd.read_parquet(tmp_path / f"s{sh}" / "scenarios" / f"part-{sh:03d}.parquet")["simulation_id"]) for sh in range(2)]
    assert ids[0] == {"sim_ds1_000000", "sim_ds1_000002", "sim_ds1_000004"} and ids[1] == {
        "sim_ds1_000001", "sim_ds1_000003", "sim_ds1_000005"}  # fmt: skip
