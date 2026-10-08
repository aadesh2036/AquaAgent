"""HTTP client for the internal sim API (BACKBONE §7.14.2).

Implementation: docs/modules/08_ORCHESTRATOR_API.md
"""

from __future__ import annotations

from shared.contracts.models import HydraulicSnapshot, SimEvent


class SimClient:
    def __init__(self, base_url: str) -> None:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")

    def create_session(self, network_id: str, seed: int, timestep_s: int = 60) -> str:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")

    def apply_event(self, session_id: str, event: SimEvent) -> None:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")

    def advance(self, session_id: str, steps: int) -> list[HydraulicSnapshot]:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")

    def snapshot(self, session_id: str) -> HydraulicSnapshot:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")

    def fork_what_if(
        self, session_id: str, events: list[SimEvent], horizon_steps: int
    ) -> list[HydraulicSnapshot]:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")

    def reset(self, session_id: str) -> HydraulicSnapshot:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")
