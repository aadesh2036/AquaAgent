"""Builds SensorWindows from snapshots — the firewall boundary (BACKBONE §7.8, §11; single 300-s cadence, §5.3).

Implementation: docs/modules/08_ORCHESTRATOR_API.md
"""

from __future__ import annotations

from shared.contracts.models import HydraulicSnapshot, SensorLayout, SensorWindow


class SensorWindowBuffer:
    def __init__(
        self, layout: SensorLayout, network_id: str, cadence_s: int = 300
    ) -> None:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")

    def push(self, snapshot: HydraulicSnapshot) -> None:
        """Extract ONLY sensor + context values (+ noise). Never keeps the snapshot."""
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")

    def window(self) -> SensorWindow | None:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")
