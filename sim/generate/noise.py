"""Sensor noise + sensor-fault injection on `measured_value` ONLY (BACKBONE §8.3, §7.2).

Implementation: docs/modules/02_DATA_GENERATION.md
"""

from __future__ import annotations

import numpy as np

from shared.contracts.models import NoiseSpec, SensorFaultSpec


def apply_noise_and_faults(
    true_values: np.ndarray,
    measurement: str,
    noise: NoiseSpec,
    faults: list[SensorFaultSpec],
    times_s: np.ndarray,
    rng: np.random.Generator,
) -> tuple[np.ndarray, list[str | None]]:
    """Return (measured_value with NaN for missing, sensor_fault_kind per row). `true_value` untouched."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/02_DATA_GENERATION.md")
