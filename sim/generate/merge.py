"""Merge shards, split by simulation, apply hard holdout, write manifest (BACKBONE §7.6, §8.5).

Implementation: docs/modules/02_DATA_GENERATION.md
"""

from __future__ import annotations

from shared.contracts.models import DatasetManifest


def assign_splits(scenarios_df, seed: int, holdout: list[str]):
    """70/15/15 by simulation_id, stratified by scenario_type; holdout locations → test only."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/02_DATA_GENERATION.md")


def merge(config_path: str, raw_uri: str, out_uri: str) -> DatasetManifest:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/02_DATA_GENERATION.md")
