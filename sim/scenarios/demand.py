"""Randomised diurnal demand profiles (BACKBONE §7.2 demand_profile, §5.3).

Implementation: docs/modules/02_DATA_GENERATION.md
"""

from __future__ import annotations

import numpy as np

from shared.contracts.models import DemandProfile


def pattern_multipliers(
    profile: DemandProfile, timestep_s: int, duration_s: int, rng: np.random.Generator
) -> np.ndarray:
    """Multiplier per timestep, indexed by `sim_time_s mod 86400`."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/02_DATA_GENERATION.md")
