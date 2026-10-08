"""Assemble Incident from AnomalyResult + LocalisationResult + evidence (BACKBONE §7.12). No ground truth.

Implementation: docs/modules/08_ORCHESTRATOR_API.md
"""

from __future__ import annotations

from shared.contracts.models import (
    AnomalyResult,
    Incident,
    LocalisationResult,
    PredictorResponse,
    SensorWindow,
)


def build_incident(
    session_id: str,
    window: SensorWindow,
    response: PredictorResponse,
    anomaly: AnomalyResult,
    localisation: LocalisationResult,
    model_versions: dict,
) -> Incident:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")
