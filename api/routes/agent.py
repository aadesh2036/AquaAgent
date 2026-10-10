"""Agent routes (BACKBONE §7.14.1): POST /api/agent/diagnose — explainable-AI report for an AI incident (module 07).

The Bedrock call (≤ 20-s budget) runs OUTSIDE the session lock so the simulator keeps stepping meanwhile.
Reports are cached per incident (one Bedrock call per incident unless ``refresh``).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


class DiagnoseRequest(BaseModel):
    incident_id: str | None = None
    """``None`` → the latest incident."""
    refresh: bool = False


@router.get("/agent/info")
def agent_info(request: Request) -> dict:
    return request.app.state.agent.info()


@router.post("/agent/diagnose")
def diagnose(body: DiagnoseRequest, request: Request) -> dict:
    app = request.app
    with app.state.holder.lock:
        mon = app.state.monitor
        iid = body.incident_id or (next(reversed(mon.incidents)) if mon.incidents else None)
        ctx = mon.incidents.get(iid) if iid else None
        if ctx is None:
            raise HTTPException(404, f"unknown incident {body.incident_id!r}" if body.incident_id else "no incident yet")
        cached = mon.reports.get(iid)
    if cached and not body.refresh:
        return cached
    runner = app.state.agent
    report = runner.diagnose(ctx).model_dump(mode="json") | {"run": dict(runner.last_run)}
    with app.state.holder.lock:
        if app.state.monitor.incidents.get(iid) is ctx:  # session not reset meanwhile
            app.state.monitor.reports[iid] = report
    return report
