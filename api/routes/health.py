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
    # predictor = the AI monitor (GNN predictor + detector) loaded; agent = Bedrock (ok) or template-only (module 07).
    predictor = HealthStatus.OK if request.app.state.monitor.enabled else HealthStatus.DEGRADED
    agent = HealthStatus.OK if request.app.state.agent.bedrock_enabled else HealthStatus.TEMPLATE
    return HealthResponse(status="ok", sim=sim, predictor=predictor, agent=agent)
