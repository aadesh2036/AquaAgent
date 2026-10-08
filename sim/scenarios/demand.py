"""Randomised diurnal demand profiles (BACKBONE §7.2 demand_profile, §5.3, §8.1).

The deterministic hourly shape comes from `sim.engine.network.diurnal_multipliers`; this module
only adds the per-simulation multiplicative noise. Implementation: docs/modules/02_DATA_GENERATION.md
"""

from __future__ import annotations

import numpy as np

from shared.contracts.models import DemandProfile
from sim.engine.network import diurnal_multipliers

MIN_MULTIPLIER = 0.05


def hourly_multipliers(profile: DemandProfile, rng: np.random.Generator) -> np.ndarray:
    """24 hourly multipliers = deterministic shape x (1 + N(0, noise_sigma)), clipped >= 0.05."""
    base = np.asarray(diurnal_multipliers(profile), dtype=float)
    noise = 1.0 + rng.normal(0.0, profile.noise_sigma, size=base.shape)
    return np.clip(base * noise, MIN_MULTIPLIER, None)
