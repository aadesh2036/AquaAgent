"""Interactive session: stepwise advance + replay-from-event-log fallback (BACKBONE §5.3, §7.3, §14).

Binding semantics
-----------------
* Fixed 300-s steps (`timestep_s != 300` -> ValueError). The session builds the pre-split network
  (`build_network(pipe_split_pos=0.5)`) and runs to t=0 on creation, so `snapshot()` is valid at once.
* **Events take effect from the NEXT step.** An event recorded at `sim_time_s == t` changes the
  state for t+300 onwards; the snapshot at t is already computed and is never altered. An event's
  `sim_time_s` must equal the session's current time, else ValueError. Invalid events (unknown
  target / params) raise ValueError and are neither applied nor logged.
* Event kinds: TAP_SET (`open`), PIPE_FAULT (`kind` LEAK|BURST|CLOSE, optional `area_m2`),
  PIPE_RESET, VALVE_SET (V1 = pipe 7 status, `open`), SPEED (logged only), RESET (== `reset()`).
  Leaks are armed with `leaks.set_leak_now` on `LK_<pipe>`; closures and valves set
  `link.initial_status` (a WNTRSimulator restart re-reads it, and the first row of the new run is
  the next step, so the closure acts from t+300; verified against a WNTR time control to ~1e-9 m).
* `advance(n)` (1..20) extends `wn.options.time.duration` and does ONE WNTRSimulator run.
* Replay mode (`replay_mode=True`) rebuilds from scratch on every `advance` and re-runs segment by
  segment through the event log with the same apply functions -> identical results.
* A WNTR failure raises `SimulationError`; the session is restored to its previous state by
  deterministic replay of the event log, and the cached snapshot / time are unchanged.
"""

from __future__ import annotations

import copy
from typing import Any

import wntr
from wntr.network import LinkStatus as WLinkStatus

from shared.contracts.ids import new_session_id
from shared.contracts.models import EventKind, HydraulicSnapshot, SimEvent
from sim.engine import network as net
from sim.engine.leaks import MAX_LEAK_AREA_M2, clear_leak_now, set_leak_now
from sim.engine.snapshot import to_snapshots

MAX_STEPS_PER_CALL = 20
DEFAULT_LEAK_AREA_M2 = 1.5e-4
DEFAULT_BURST_AREA_M2 = 2.0e-3
_FAULT_KINDS = {"LEAK", "BURST", "CLOSE"}


class SimulationError(RuntimeError):
    """WNTR failed to solve; the session was left at its previous state."""


def _need_bool(params: dict[str, Any], key: str = "open") -> bool:
    if set(params) != {key} or not isinstance(params[key], bool):
        raise ValueError(f"params must be exactly {{'{key}': bool}}, got {params!r}")
    return params[key]


def _parse(event: SimEvent) -> tuple | None:
    """Validate an event and turn it into an action tuple (None = log only). Raises ValueError."""
    kind, target, params = event.kind, event.target_id, dict(event.params)
    if kind == EventKind.TAP_SET:
        if target not in net.TAPS:
            raise ValueError(f"unknown tap {target!r}")
        return ("tap", net.TAPS[target], _need_bool(params))
    if kind == EventKind.PIPE_FAULT:
        if target not in net.LEAK_PIPES:
            raise ValueError(f"unknown pipe {target!r}")
        fkind = params.get("kind")
        if fkind not in _FAULT_KINDS or not set(params) <= {"kind", "area_m2"}:
            raise ValueError(f"bad PIPE_FAULT params {params!r}")
        if fkind == "CLOSE":
            if "area_m2" in params:
                raise ValueError("CLOSE takes no area_m2")
            return ("status", target, WLinkStatus.Closed)
        area = params.get("area_m2", DEFAULT_LEAK_AREA_M2 if fkind == "LEAK" else DEFAULT_BURST_AREA_M2)
        if isinstance(area, bool) or not isinstance(area, int | float) or not 0 < area <= MAX_LEAK_AREA_M2:
            raise ValueError(f"area_m2 must be in (0, {MAX_LEAK_AREA_M2}], got {area!r}")
        return ("leak", f"LK_{target}", float(area))
    if kind == EventKind.PIPE_RESET:
        if target not in net.LEAK_PIPES or params:
            raise ValueError(f"bad PIPE_RESET {target!r} {params!r}")
        return ("reset_pipe", target)
    if kind == EventKind.VALVE_SET:
        if target not in net.VALVES:
            raise ValueError(f"unknown valve {target!r}")
        is_open = _need_bool(params)
        return ("status", net.VALVES[target], WLinkStatus.Opened if is_open else WLinkStatus.Closed)
    if kind in (EventKind.SPEED, EventKind.RESET):
        return None
    raise ValueError(f"unsupported event kind {kind!r}")


def _apply_action(wn, action: tuple | None) -> None:
    """The ONE place events change the model (shared by stepwise, fork and replay)."""
    if action is None:
        return
    op = action[0]
    if op == "tap":
        _, node, is_open = action
        for d in wn.get_node(node).demand_timeseries_list:
            if d.category == net.TAP_DEMAND_CATEGORY:
                d.base_value = net.TAP_EXTRA_DEMAND_M3S if is_open else 0.0
    elif op == "status":
        wn.get_link(action[1]).initial_status = action[2]
    elif op == "leak":
        set_leak_now(wn, action[1], action[2])
    elif op == "reset_pipe":
        clear_leak_now(wn, f"LK_{action[1]}")
        wn.get_link(action[1]).initial_status = WLinkStatus.Opened


def _run_to(wn, t_s: int):
    wn.options.time.duration = t_s
    try:
        return wntr.sim.WNTRSimulator(wn).run_sim()
    except Exception as exc:  # WNTR raises assorted types on non-convergence
        raise SimulationError(f"WNTR failed advancing to t={t_s}s: {exc}") from exc


class SimSession:
    """One interactive session. Event log + seed must replay exactly (§7.3, P4)."""

    def __init__(
        self,
        network_id: str = net.NETWORK_ID,
        seed: int = 0,
        timestep_s: int = net.TIMESTEP_S,
        *,
        replay_mode: bool = False,
    ) -> None:
        if timestep_s != net.TIMESTEP_S:
            raise ValueError(f"only {net.TIMESTEP_S}-s steps are supported, got {timestep_s}")
        if network_id != net.NETWORK_ID:
            raise ValueError(f"unknown network_id {network_id!r}")
        self.session_id = new_session_id()
        self.network_id = network_id
        self.seed = seed
        self.timestep_s = timestep_s
        self.replay_mode = replay_mode
        self.sim_time_s = 0
        self.events: list[SimEvent] = []
        self._init_state()

    def _init_state(self) -> None:
        self.wn = net.build_network(self.network_id, pipe_split_pos=0.5, duration_s=0)
        self.sim_time_s = 0
        self.events = []
        self._snap = to_snapshots(_run_to(self.wn, 0), self.network_id, self.wn)[-1]

    # ------------------------------------------------------------------ events
    def apply_event(self, event: SimEvent) -> None:
        """Validate, append to the log and apply to the model; effective from the next step."""
        if event.sim_time_s != self.sim_time_s:
            raise ValueError(f"event time {event.sim_time_s} != session time {self.sim_time_s}")
        action = _parse(event)
        if event.kind == EventKind.RESET:
            self.reset()
            return
        if not self.replay_mode:
            _apply_action(self.wn, action)
        self.events.append(event)

    # ----------------------------------------------------------------- advance
    def advance(self, steps: int) -> list[HydraulicSnapshot]:
        """Advance `steps` x 300 s (1..20). Returns one snapshot per new step, incl. `hidden`."""
        if not isinstance(steps, int) or not 1 <= steps <= MAX_STEPS_PER_CALL:
            raise ValueError(f"steps must be in 1..{MAX_STEPS_PER_CALL}, got {steps!r}")
        target = self.sim_time_s + steps * self.timestep_s
        try:
            if self.replay_mode:
                wn, snaps = self._replay(target)
            else:
                snaps = to_snapshots(_run_to(self.wn, target), self.network_id, self.wn)
                wn = self.wn
        except SimulationError:
            if not self.replay_mode:
                self.wn = self._replay(self.sim_time_s)[0]  # roll back by deterministic replay
            raise
        self.wn = wn
        self.sim_time_s = target
        self._snap = snaps[-1]
        return snaps

    def _replay(self, target: int):
        """Rebuild from scratch and re-run segment by segment with the event log up to `target`."""
        wn = net.build_network(self.network_id, pipe_split_pos=0.5, duration_s=0)
        _run_to(wn, 0)
        t = 0
        out: list[HydraulicSnapshot] = []
        for ev in sorted(self.events, key=lambda e: e.sim_time_s):  # stable
            if ev.sim_time_s > target:
                break
            if ev.sim_time_s > t:
                out += to_snapshots(_run_to(wn, ev.sim_time_s), self.network_id, wn)
                t = ev.sim_time_s
            _apply_action(wn, _parse(ev))
        if target > t:
            out += to_snapshots(_run_to(wn, target), self.network_id, wn)
        return wn, [s for s in out if s.sim_time_s > self.sim_time_s] or out[-1:]

    # ------------------------------------------------------------------ queries
    def snapshot(self) -> HydraulicSnapshot:
        """Current full-truth snapshot, including `hidden` (§7.14.2)."""
        return self._snap

    def reset(self) -> HydraulicSnapshot:
        """Fresh build, t=0, event log cleared."""
        self._init_state()
        return self._snap

    def fork_what_if(self, events: list[SimEvent], horizon_steps: int) -> list[HydraulicSnapshot]:
        """Run on a FORKED copy — never mutates the live session (§7.13 run_what_if)."""
        if horizon_steps < 1:
            raise ValueError("horizon_steps must be >= 1")
        child = object.__new__(SimSession)
        child.__dict__.update(copy.copy(self.__dict__))
        child.wn = copy.deepcopy(self.wn)
        child.events = list(self.events)
        for ev in events:
            child.apply_event(ev)
        out: list[HydraulicSnapshot] = []
        remaining = horizon_steps
        while remaining > 0:
            n = min(MAX_STEPS_PER_CALL, remaining)
            out += child.advance(n)
            remaining -= n
        return out
