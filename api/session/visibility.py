"""Visibility filter: HydraulicSnapshot → NetworkView, hidden stripped (BACKBONE §7.14.1, §11).

Implementation: docs/modules/08_ORCHESTRATOR_API.md
"""

from __future__ import annotations

from shared.contracts.models import HydraulicSnapshot, NetworkView


def to_network_view(snapshot: HydraulicSnapshot, session_state, reveal: bool = False) -> NetworkView:
    """Convert units via shared.units; drop `hidden`, LK_*, hidden events; visual_fault NONE for hidden faults."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")
