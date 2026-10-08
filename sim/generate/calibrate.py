"""Leak-size calibration → config/generation/ds1.yaml (BACKBONE §8.1, G2).

Implementation: docs/modules/02_DATA_GENERATION.md
"""

from __future__ import annotations


def calibrate(config_path: str) -> dict:
    """Measure realised leak flow / total system demand per location × area; propose bucket ranges."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/02_DATA_GENERATION.md")
