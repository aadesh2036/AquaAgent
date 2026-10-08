"""Mass-balance check (BACKBONE §7.4, G1): Σ source outflow ≈ Σ delivered demand + Σ leak, tol 1e-4 m³/s.

Implementation: docs/modules/01_SIMULATION_ENGINE.md
"""

from __future__ import annotations

from shared.contracts.models import HydraulicSnapshot

MASS_BALANCE_TOL_M3S = 1e-4


def mass_balance_error_m3s(snapshot: HydraulicSnapshot) -> float:
    """Signed imbalance in m³/s (reservoir + tank outflow − demand − leak)."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/01_SIMULATION_ENGINE.md")


def check_mass_balance(snapshot: HydraulicSnapshot, tol_m3s: float = MASS_BALANCE_TOL_M3S) -> bool:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/01_SIMULATION_ENGINE.md")
