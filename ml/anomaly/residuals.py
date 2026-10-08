"""LOO residuals and z-scores (BACKBONE §9.2, §7.10).

Implementation: docs/modules/05_ANOMALY_LOCALISATION.md
"""

from __future__ import annotations

from shared.contracts.models import PredictorResponse, ResidualFrame, SensorWindow


def residual_frame(
    window: SensorWindow, response: PredictorResponse, sigmas: dict[str, float]
) -> ResidualFrame:
    """r_s = observed_s − LOO_prediction_s; z_s = r_s / σ_s (σ from val-normal)."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/05_ANOMALY_LOCALISATION.md")


def estimate_sigmas(val_normal_residuals) -> dict[str, float]:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/05_ANOMALY_LOCALISATION.md")
