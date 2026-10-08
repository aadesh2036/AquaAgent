"""GET /api/health (BACKBONE §7.14.1; ALB health check §3.2).

Implementation: docs/modules/08_ORCHESTRATOR_API.md
"""

from __future__ import annotations

from shared.contracts.models import HealthResponse


def health() -> HealthResponse:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")
