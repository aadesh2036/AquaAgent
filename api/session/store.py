"""Single in-memory interactive session (BACKBONE §5.3; module 08 §5)."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from api.session.event_log import EventLog
from shared.contracts.models import HydraulicSnapshot, VisualFault

VALID_SPEEDS = (1, 5, 20)


@dataclass
class SessionState:
    sim_session_id: str
    seed: int
    snapshot: HydraulicSnapshot
    speed: int = 1
    taps: dict[str, bool] = field(default_factory=lambda: {"T1": False, "T2": False, "T3": False})
    valves: dict[str, bool] = field(default_factory=lambda: {"V1": True})
    visual_faults: dict[str, VisualFault] = field(default_factory=dict)
    events: EventLog = field(default_factory=EventLog)

    @property
    def sim_time_s(self) -> int:
        return self.snapshot.sim_time_s


class SessionHolder:
    """Holds the one session. Routes take `.lock` for the whole request."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.state: SessionState | None = None
