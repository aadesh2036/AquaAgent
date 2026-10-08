"""GET /api/health (BACKBONE §7.14.1; ALB health check §3.2)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from api.clients.sim_client import SimUnavailable
from shared.contracts.models import HealthResponse, HealthStatus

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    try:
        request.app.state.sim_client.health()
        sim = "ok"
    except SimUnavailable:
        sim = "down"
    # predictor arrives with module 08 step 3; agent is the template reporter in T1.
    return HealthResponse(
        status="ok", sim=sim, predictor=HealthStatus.DEGRADED, agent=HealthStatus.TEMPLATE
    )
