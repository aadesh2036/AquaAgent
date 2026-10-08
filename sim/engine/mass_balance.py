"""Mass-balance check (BACKBONE §7.4, G1): Σ source outflow ≈ Σ delivered demand + Σ leak, tol 1e-4 m³/s."""

from __future__ import annotations

from shared.contracts.models import HydraulicSnapshot

MASS_BALANCE_TOL_M3S = 1e-4


def mass_balance_error_m3s(snapshot: HydraulicSnapshot) -> float:
    """Signed imbalance in m³/s: Σ node demand (reservoir negative, tank positive when filling)
    + Σ junction leak + Σ hidden (pipe) leak. Zero for a balanced network."""
    total = sum(n.demand_m3s + n.leak_m3s for n in snapshot.nodes.values())
    if snapshot.hidden is not None:
        total += sum(v.leak_m3s for v in snapshot.hidden.leak_nodes.values())
    return float(total)


def check_mass_balance(snapshot: HydraulicSnapshot, tol_m3s: float = MASS_BALANCE_TOL_M3S) -> bool:
    return abs(mass_balance_error_m3s(snapshot)) <= tol_m3s


def results_mass_balance_error(results) -> float:
    """max over time of |Σ demand + Σ leak_demand| over ALL result nodes (incl. LK_*, reservoir, tank)."""
    total = results.node["demand"].sum(axis=1) + results.node["leak_demand"].sum(axis=1)
    return float(total.abs().max())
