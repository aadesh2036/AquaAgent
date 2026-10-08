"""Run one shard of simulations (BACKBONE §8.6).

Implementation: docs/modules/02_DATA_GENERATION.md
"""

from __future__ import annotations

from shared.contracts.models import ScenarioSpec


def run_simulation(spec: ScenarioSpec):  # -> (tables: dict[str, DataFrame], validation_rows)
    """Simulate one spec with WNTRSimulator at 300 s for 24 h (289 snapshots)."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/02_DATA_GENERATION.md")


def run_shard(config_path: str, shard: int, num_shards: int, out_uri: str, limit: int | None = None) -> None:
    """Simulate specs where `sim_index % num_shards == shard`; write Parquet to `out_uri`."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/02_DATA_GENERATION.md")
