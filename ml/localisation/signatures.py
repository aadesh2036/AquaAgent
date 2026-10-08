"""Offline signature dictionary: 14 locations × 3 sizes × 4 ToD (BACKBONE §9.4, BI-03).

Implementation: docs/modules/05_ANOMALY_LOCALISATION.md
"""

from __future__ import annotations


def generate_signatures(network_config_path: str, predictor_artifact: str | None, out_path: str) -> str:
    """Uses the sim engine (module 01) to simulate leak vs no-leak twins. Returns signatures_version."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/05_ANOMALY_LOCALISATION.md")
