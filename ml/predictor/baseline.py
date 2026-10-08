"""Nearest-sensor + elevation-corrected baseline (BACKBONE §9.1 rung 1).

Implementation: docs/modules/04_ML_PREDICTOR.md
"""

from __future__ import annotations


def predict_nearest_sensor(observed_pressure_m: dict[str, float | None], config) -> dict[str, float]:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/04_ML_PREDICTOR.md")
