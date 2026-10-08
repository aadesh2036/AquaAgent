"""Sample ScenarioSpecs for every scenario type in BACKBONE §8.1.

Implementation: docs/modules/02_DATA_GENERATION.md
"""

from __future__ import annotations

import numpy as np

from shared.contracts.models import ScenarioSpec, ScenarioType


def sample_scenario(
    scenario_type: ScenarioType, sim_index: int, dataset_version: str, rng: np.random.Generator, gen_cfg: dict
) -> ScenarioSpec:
    """One spec. All randomness via `rng` = Generator(PCG64(seed)) (§5.4)."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/02_DATA_GENERATION.md")


def plan_dataset(gen_cfg: dict, dataset_seed: int) -> list[ScenarioSpec]:
    """Full ds plan (counts §8.1), deterministic from `dataset_seed`."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/02_DATA_GENERATION.md")


def sim_seed(dataset_seed: int, sim_index: int) -> int:
    """`hash64(dataset_seed, sim_index)` (§5.4)."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/02_DATA_GENERATION.md")
