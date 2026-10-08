"""Append-only event log (BACKBONE §7.3).

Implementation: docs/modules/08_ORCHESTRATOR_API.md
"""

from __future__ import annotations

from shared.contracts.models import SimEvent


class EventLog:
    def append(self, event: SimEvent) -> None:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")

    def public_events(self) -> list[SimEvent]:
        """Events with hidden=False only (until reveal)."""
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")
