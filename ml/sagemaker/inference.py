"""SageMaker inference handlers (T2b) implementing BACKBONE §7.9 via ml.predictor.predict (one call).

Placed at `code/inference.py` inside model.tar.gz.

Implementation: docs/modules/06_SAGEMAKER.md
"""

from __future__ import annotations

from typing import Any


def model_fn(model_dir: str) -> Any:
    """Load model weights + scalers.json from model.tar.gz (BI-09)."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/06_SAGEMAKER.md")


def input_fn(request_body: str | bytes, content_type: str = "application/json") -> Any:
    """Parse and validate a PredictorRequest (§7.9)."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/06_SAGEMAKER.md")


def predict_fn(request: Any, model: Any) -> dict:
    """Return PredictorResponse dict with reconstruct + leave_one_out + latency_ms."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/06_SAGEMAKER.md")


def output_fn(prediction: dict, accept: str = "application/json") -> str:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/06_SAGEMAKER.md")
