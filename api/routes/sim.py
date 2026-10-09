"""Session/network/sim/tap/pipe/valve routes (BACKBONE §7.14.1)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from api.app.settings import Settings
from api.clients.sim_client import SimRejected
from api.session.store import VALID_SPEEDS, SessionState
from api.session.visibility import to_network_view
from shared.contracts.models import (
    EventKind,
    EventSource,
    LinkType,
    NetworkConfig,
    NetworkTopology,
    NetworkView,
    PipeFaultKind,
    PipeFaultRequest,
    SensorLayout,
    SessionResetRequest,
    SimStepRequest,
    TapRequest,
    ValveRequest,
    VisualFault,
)

router = APIRouter()


def load_topology(settings: Settings) -> tuple[NetworkTopology, SensorLayout]:
    cfg = settings.config_dir
    net = NetworkConfig.model_validate(
        json.loads(Path(cfg, "networks", f"{settings.network_id}.json").read_text())
    )
    layout = SensorLayout.model_validate(
        json.loads(Path(cfg, "sensors", f"{settings.sensor_layout_id}.json").read_text())
    )
    topo = NetworkTopology(
        schema_version=net.schema_version,
        network_id=net.network_id,
        nodes=net.nodes,
        links=net.links,
        zones=net.zones,
        taps=net.taps,
        valves=net.valves,
        sensor_layout=layout,
    )
    return topo, layout


def _new_state(request: Request, seed: int) -> SessionState:
    app = request.app
    sim = app.state.sim_client
    sid = sim.create_session(app.state.settings.network_id, seed)
    snap = sim.snapshot(sid)
    app.state.monitor.reset(seed)
    app.state.monitor.observe([snap])
    return SessionState(sim_session_id=sid, seed=seed, snapshot=snap)


def _ensure(request: Request) -> SessionState:
    holder = request.app.state.holder
    if holder.state is None:
        holder.state = _new_state(request, 0)
    return holder.state


def _run(request: Request, fn: Callable[[SessionState], None]) -> NetworkView:
    """Run `fn(state)` under the session lock and return the view.

    If the sim answers 404 (restarted / LRU-evicted session), start a fresh sim session with the same
    seed, reset the api state (speed kept), log a public system event and retry `fn` once.
    """
    holder = request.app.state.holder
    with holder.lock:
        state = _ensure(request)
        try:
            fn(state)
        except SimRejected as exc:
            if exc.status_code != 404:
                raise
            speed = state.speed
            state = holder.state = _new_state(request, state.seed)
            state.speed = speed
            state.events.append(
                sim_time_s=0,
                source=EventSource.SYSTEM,
                kind=EventKind.RESET,
                target_id=None,
                params={},
                text="Simulation restarted — session reset",
            )
            fn(state)
        return _view(request, state)


def _view(request: Request, state: SessionState) -> NetworkView:
    app = request.app
    view = to_network_view(
        state.snapshot, state, app.state.topology, app.state.layout, app.state.settings.tank_max_level_m
    )
    return view.model_copy(update={"network_status": app.state.monitor.network_status})


@router.post("/session/reset", response_model=NetworkView)
def session_reset(request: Request, body: SessionResetRequest | None = None) -> NetworkView:
    seed = body.seed if body and body.seed is not None else 0
    holder = request.app.state.holder
    with holder.lock:
        holder.state = _new_state(request, seed)
        return _view(request, holder.state)


@router.get("/network/topology", response_model=NetworkTopology)
def network_topology(request: Request) -> NetworkTopology:
    return request.app.state.topology


@router.get("/network/state", response_model=NetworkView)
def network_state(request: Request) -> NetworkView:

    def go(state: SessionState) -> None:
        state.snapshot = request.app.state.sim_client.snapshot(state.sim_session_id)

    return _run(request, go)


@router.post("/sim/step", response_model=NetworkView)
def sim_step(request: Request, body: SimStepRequest) -> NetworkView:

    def go(state: SessionState) -> None:
        snaps = request.app.state.sim_client.advance(state.sim_session_id, body.steps)
        state.snapshot = snaps[-1]
        request.app.state.monitor.observe(snaps)  # AI listens to every 300-s step (SensorWindow only)
        if body.steps in VALID_SPEEDS:
            state.speed = body.steps

    return _run(request, go)


def _emit(
    request: Request, state: SessionState, kind: EventKind, target: str, params: dict, text: str
) -> None:
    """Log the event (UI text included) and send it to the sim at the current session time."""
    ev = state.events.append(
        sim_time_s=state.sim_time_s,
        source=EventSource.USER,
        kind=kind,
        target_id=target,
        params=params,
        text=text,
    )
    request.app.state.sim_client.apply_event(state.sim_session_id, ev)


@router.post("/tap", response_model=NetworkView)
def tap(request: Request, body: TapRequest) -> NetworkView:
    app = request.app
    if body.tap_id not in {t.tap_id for t in app.state.topology.taps}:
        raise HTTPException(422, f"unknown tap {body.tap_id!r}")
    text = f"Tap {body.tap_id} {'opened' if body.open else 'closed'}"

    def go(state: SessionState) -> None:
        _emit(request, state, EventKind.TAP_SET, body.tap_id, {"open": body.open}, text)
        state.taps[body.tap_id] = body.open

    return _run(request, go)


@router.post("/pipe/fault", response_model=NetworkView)
def pipe_fault(request: Request, body: PipeFaultRequest) -> NetworkView:
    app = request.app
    pipes = {lk.link_id for lk in app.state.topology.links if lk.link_type == LinkType.PIPE}
    if body.link_id not in pipes:
        raise HTTPException(422, f"unknown pipe {body.link_id!r}")
    lid = body.link_id

    def go(state: SessionState) -> None:
        if body.kind == PipeFaultKind.RESET:
            _emit(request, state, EventKind.PIPE_RESET, lid, {}, f"Pipe {lid} reset")
            state.visual_faults.pop(lid, None)
            app.state.monitor.operator_repair()  # public user action → AI re-arms (BI-27)
            for v in app.state.topology.valves:  # a valve is a pipe status; reset reopens it
                if v.link_id == lid:
                    state.valves[v.valve_id] = True
        else:
            word = {"LEAK": "Leak on pipe", "BURST": "Burst on pipe", "CLOSE": "Closed pipe"}[body.kind.value]
            _emit(request, state, EventKind.PIPE_FAULT, lid, {"kind": body.kind.value}, f"{word} {lid}")
            if body.kind == PipeFaultKind.LEAK:
                state.visual_faults[lid] = VisualFault.LEAK
            elif body.kind == PipeFaultKind.BURST:
                state.visual_faults[lid] = VisualFault.BURST
            # CLOSE changes only link status (comes from the physics)

    return _run(request, go)


@router.post("/valve", response_model=NetworkView)
def valve(request: Request, body: ValveRequest) -> NetworkView:
    app = request.app
    if body.valve_id not in {v.valve_id for v in app.state.topology.valves}:
        raise HTTPException(422, f"unknown valve {body.valve_id!r}")
    text = f"Valve {body.valve_id} {'opened' if body.open else 'closed'}"

    def go(state: SessionState) -> None:
        _emit(request, state, EventKind.VALVE_SET, body.valve_id, {"open": body.open}, text)
        state.valves[body.valve_id] = body.open

    return _run(request, go)
