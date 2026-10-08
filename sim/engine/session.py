"""Interactive session: stepwise advance + replay-from-event-log fallback (BACKBONE §5.3, §7.3, §14).

Implementation: docs/modules/01_SIMULATION_ENGINE.md
"""

from __future__ import annotations

from shared.contracts.models import HydraulicSnapshot, SimEvent


class SimSession:
    """One interactive session. Event log + seed must replay exactly (§7.3, P4)."""

    def __init__(self, network_id: str, seed: int, timestep_s: int = 60) -> None:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/01_SIMULATION_ENGINE.md")

    def apply_event(self, event: SimEvent) -> None:
        """Append to the event log and apply to the model (§7.3)."""
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/01_SIMULATION_ENGINE.md")

    def advance(self, steps: int) -> list[HydraulicSnapshot]:
        """Advance `steps` × timestep. Uses stepwise WNTRSimulator; falls back to replay (§14)."""
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/01_SIMULATION_ENGINE.md")

    def snapshot(self) -> HydraulicSnapshot:
        """Current full-truth snapshot, including `hidden` (§7.14.2)."""
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/01_SIMULATION_ENGINE.md")

    def fork_what_if(self, events: list[SimEvent], horizon_steps: int) -> list[HydraulicSnapshot]:
        """Run on a FORKED copy — never mutates the live session (§7.13 run_what_if)."""
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/01_SIMULATION_ENGINE.md")

    def reset(self) -> HydraulicSnapshot:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/01_SIMULATION_ENGINE.md")
