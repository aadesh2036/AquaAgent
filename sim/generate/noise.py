"""Sensor noise + sensor-fault injection on `measured_value` ONLY (BACKBONE §8.3, §7.2).

`true_value` is never touched. ds1 has no sensor faults (they are ds2); the fault kinds are
implemented here so ds2 needs no change.

Implementation: docs/modules/02_DATA_GENERATION.md
"""

from __future__ import annotations

import numpy as np

from shared.contracts.models import NoiseSpec, SensorFaultKind, SensorFaultSpec

_SIGMA_FIELD = {"pressure_m": "pressure_sigma_m", "flow_lps": "flow_sigma_lps"}


def apply_noise_and_faults(
    true_values: np.ndarray,
    measurement: str,
    noise: NoiseSpec,
    faults: list[SensorFaultSpec],
    times_s: np.ndarray,
    rng: np.random.Generator,
) -> tuple[np.ndarray, list[str | None]]:
    """Return (measured_value with NaN for missing, sensor_fault_kind per row). `true_value` untouched."""
    true_values = np.asarray(true_values, dtype=float)
    times_s = np.asarray(times_s)
    sigma = getattr(noise, _SIGMA_FIELD[measurement])
    measured = true_values + (rng.normal(0.0, sigma, size=true_values.shape) if sigma > 0 else 0.0)
    kinds: list[str | None] = [None] * len(true_values)
    for f in faults:
        end = f.end_s if f.end_s is not None else np.inf
        idx = np.flatnonzero((times_s >= f.start_s) & (times_s < end))
        if idx.size == 0:
            continue
        mag = f.magnitude if f.magnitude is not None else 0.0
        if f.kind == SensorFaultKind.BIAS:
            measured[idx] += mag
        elif f.kind == SensorFaultKind.DRIFT:
            measured[idx] += mag * (times_s[idx] - f.start_s) / 3600.0
        elif f.kind == SensorFaultKind.STUCK:
            measured[idx] = measured[idx[0]]
        elif f.kind == SensorFaultKind.SPIKE:
            measured[idx] += mag
        elif f.kind == SensorFaultKind.MISSING:
            measured[idx] = np.nan
        for i in idx:
            kinds[i] = f.kind.value
    if noise.missing_rate > 0:
        measured[rng.random(measured.shape) < noise.missing_rate] = np.nan
    return measured, kinds
