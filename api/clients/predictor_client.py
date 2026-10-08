"""PredictorClient: AQUA_MODE=local loads model.tar.gz in-process; aws invokes SageMaker (BACKBONE §3.3).

The ONLY accepted input is SensorWindow (§7.8, §11 firewall).

Implementation: docs/modules/08_ORCHESTRATOR_API.md
"""

from __future__ import annotations

from shared.contracts.models import PredictorResponse, SensorWindow


class PredictorClient:
    def predict(self, window: SensorWindow) -> PredictorResponse:
        """Signature is the firewall: nothing but a SensorWindow may enter (§11)."""
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")
