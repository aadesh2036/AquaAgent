"""Build GraphSamples from `sensors` + `context` + `graph` ONLY (BACKBONE §7.7, §11).

Implementation: docs/modules/04_ML_PREDICTOR.md
"""

from __future__ import annotations

from shared.contracts.models import EDGE_FEATURES_V1, NODE_FEATURES_V1, SensorWindow  # noqa: F401


def build_split(processed_uri: str, split: str, scalers: dict, out_path: str) -> None:
    """Write features/<ds>/<split>.pt. Inputs: sensors.measured_value, context, graph. Targets: node_states."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/04_ML_PREDICTOR.md")


def window_to_features(window: SensorWindow, scalers: dict, mask_sensor: str | None = None):
    """Online path used by inference.py — identical maths to the offline builder."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/04_ML_PREDICTOR.md")
