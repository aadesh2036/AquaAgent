"""Map WNTR results to canonical HydraulicSnapshot (BACKBONE §7.4): `4_B`→`4`, `LK_*`→hidden.

Implementation: docs/modules/01_SIMULATION_ENGINE.md
"""

from __future__ import annotations

from shared.contracts.models import HydraulicSnapshot, NetworkConfig


def to_snapshot(results, t_s: int, config: NetworkConfig) -> HydraulicSnapshot:
    """Canonical snapshot at time `t_s`. Canonical link reports the UPSTREAM half's flow (§7.4)."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/01_SIMULATION_ENGINE.md")
