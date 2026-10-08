"""Predict API: SensorWindow → PredictorResponse (BACKBONE §7.8, §7.9). Used by 06 inference.py and 08 local client.

Implementation: docs/modules/04_ML_PREDICTOR.md
"""

from __future__ import annotations

from shared.contracts.models import PredictorResponse, SensorWindow


def load_artifact(model_dir: str):
    """Load model.pt + scalers.json + meta.json from an extracted model.tar.gz (BI-09)."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/04_ML_PREDICTOR.md")


def predict(window: SensorWindow, artifact, model_version: str) -> PredictorResponse:
    """reconstruct + leave_one_out (S1–S3) + leave_one_out_flow (F1–F2) from one 6-row batch (§7.9)."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/04_ML_PREDICTOR.md")
