"""In-memory event log (BACKBONE §7.3). Events carry UI text; hidden ones never leave the api."""

from __future__ import annotations

from shared.contracts.models import EventKind, EventSource, SimEvent, ViewEvent


class EventLog:
    def __init__(self) -> None:
        self._events: list[SimEvent] = []
        self._text: dict[str, str] = {}

    def next_id(self) -> str:
        return f"ev_{len(self._events) + 1:04d}"

    def append(
        self,
        *,
        sim_time_s: int,
        source: EventSource,
        kind: EventKind,
        target_id: str | None,
        params: dict,
        text: str,
        hidden: bool = False,
    ) -> SimEvent:
        ev = SimEvent(
            event_id=self.next_id(),
            sim_time_s=sim_time_s,
            source=source,
            kind=kind,
            target_id=target_id,
            params=params,
            hidden=hidden,
        )
        self._events.append(ev)
        self._text[ev.event_id] = text
        return ev

    def all(self) -> list[SimEvent]:
        return list(self._events)

    def text_of(self, event_id: str) -> str:
        return self._text[event_id]

    def public_events(self, limit: int = 20) -> list[ViewEvent]:
        """Most recent `limit` non-hidden events, oldest first."""
        vis = [e for e in self._events if not e.hidden]
        return [ViewEvent(sim_time_s=e.sim_time_s, text=self._text[e.event_id]) for e in vis[-limit:]]
