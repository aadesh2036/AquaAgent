"""FastAPI app for BACKBONE §7.14.2. Returns full truth; the orchestrator enforces visibility.

Must not import boto3 (BACKBONE_ISSUES BI-11).

Sessions live in memory (LRU-evicted beyond `max_sessions`); each has its own lock because the
endpoints are sync and run in FastAPI's threadpool.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict

import wntr
from fastapi import FastAPI, HTTPException, Request

from shared.contracts.models import (
    CONTRACT_VERSION,
    ForkWhatIfRequest,
    HydraulicSnapshot,
    SimAdvanceRequest,
    SimEvent,
    SimEventApplied,
    SimHealthResponse,
    SimSessionCreateRequest,
    SimSessionCreateResponse,
)
from sim.engine.session import SimSession, SimulationError

log = logging.getLogger("aquaagent.sim.server")


class SessionStore:
    """LRU store of sessions with per-session locks."""

    def __init__(self, max_sessions: int) -> None:
        self.max_sessions = max_sessions
        self._items: OrderedDict[str, tuple[SimSession, threading.Lock]] = OrderedDict()
        self._lock = threading.Lock()

    def add(self, session: SimSession) -> None:
        with self._lock:
            self._items[session.session_id] = (session, threading.Lock())
            while len(self._items) > self.max_sessions:
                old, _ = self._items.popitem(last=False)
                log.info("evicted session %s", old)

    def get(self, session_id: str) -> tuple[SimSession, threading.Lock]:
        with self._lock:
            if session_id not in self._items:
                raise HTTPException(status_code=404, detail=f"unknown session {session_id!r}")
            self._items.move_to_end(session_id)
            return self._items[session_id]


def create_app(max_sessions: int = 8) -> FastAPI:
    """Routes: GET /sim/health, POST /sim/session, POST /sim/session/{id}/event,
    POST /sim/session/{id}/advance, GET /sim/session/{id}/snapshot,
    POST /sim/session/{id}/fork_what_if, POST /sim/session/{id}/reset (§7.14.2)."""
    app = FastAPI(title="AquaAgent sim engine", version=CONTRACT_VERSION)
    store = SessionStore(max_sessions)

    @app.middleware("http")
    async def contract_header(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Aqua-Contract"] = CONTRACT_VERSION
        return response

    @app.get("/sim/health", response_model=SimHealthResponse)
    def health() -> SimHealthResponse:
        return SimHealthResponse(status="ok", wntr_version=wntr.__version__)

    @app.post("/sim/session", response_model=SimSessionCreateResponse)
    def create_session(req: SimSessionCreateRequest) -> SimSessionCreateResponse:
        try:
            session = SimSession(req.network_id, req.seed, req.timestep_s)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        store.add(session)
        log.info("created session %s", session.session_id)
        return SimSessionCreateResponse(session_id=session.session_id)

    @app.post("/sim/session/{session_id}/event", response_model=SimEventApplied)
    def apply_event(session_id: str, event: SimEvent) -> SimEventApplied:
        session, lock = store.get(session_id)
        with lock:
            try:
                session.apply_event(event)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        return SimEventApplied(applied=True)

    @app.post("/sim/session/{session_id}/advance", response_model=list[HydraulicSnapshot])
    def advance(session_id: str, req: SimAdvanceRequest) -> list[HydraulicSnapshot]:
        session, lock = store.get(session_id)
        with lock:
            try:
                return session.advance(req.steps)
            except SimulationError as exc:
                log.error("simulation error in %s: %s", session_id, exc)
                raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/sim/session/{session_id}/snapshot", response_model=HydraulicSnapshot)
    def snapshot(session_id: str) -> HydraulicSnapshot:
        session, lock = store.get(session_id)
        with lock:
            return session.snapshot()

    @app.post("/sim/session/{session_id}/fork_what_if", response_model=list[HydraulicSnapshot])
    def fork_what_if(session_id: str, req: ForkWhatIfRequest) -> list[HydraulicSnapshot]:
        session, lock = store.get(session_id)
        with lock:
            try:
                return session.fork_what_if(req.events, req.horizon_steps)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            except SimulationError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/sim/session/{session_id}/reset", response_model=HydraulicSnapshot)
    def reset(session_id: str) -> HydraulicSnapshot:
        session, lock = store.get(session_id)
        with lock:
            return session.reset()

    return app


app = create_app()
