"""Shared fixtures for the module-02 tests."""

from __future__ import annotations

import pytest

from sim.generate.merge import merge
from sim.generate.runner import run_shard

CONFIG = "config/generation/ds1.yaml"


@pytest.fixture(scope="session")
def smoke_dataset(tmp_path_factory):
    """16-sim shard -> merge. Returns (raw_dir, processed_dir, manifest)."""
    base = tmp_path_factory.mktemp("ds_smoke")
    raw, out = str(base / "raw"), str(base / "processed")
    run_shard(CONFIG, 0, 1, f"{raw}/shard=0/", limit=16)
    manifest = merge(CONFIG, raw, out)
    return raw, out, manifest
