"""AI monitor routes: GET /api/ai/state, POST /api/ai/ack (owner request 2026-10-09; BI-27).

Everything returned is derived from the SensorWindow pipeline (§11): AI reconstruction of every node, leave-one-out
estimates at the sensors, detector status + score history, notifications and the 'BY AI' highlight.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/ai/state")
def ai_state(request: Request) -> dict:
    with request.app.state.holder.lock:
        return request.app.state.monitor.state()


@router.post("/ai/ack")
def ai_ack(request: Request) -> dict:
    with request.app.state.holder.lock:
        request.app.state.monitor.acknowledge()
        return request.app.state.monitor.state()
