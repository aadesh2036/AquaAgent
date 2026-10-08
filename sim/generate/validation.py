"""Per-simulation validation checks → validation_log (BACKBONE §8.4).

One `ValidationLogRow` per check in `VALIDATION_CHECKS`, pass or fail. Any failure excludes the
simulation from the dataset tables (the log rows are kept).

Implementation: docs/modules/02_DATA_GENERATION.md
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from shared.contracts.models import (
    FLOW_SENSORS,
    OPERATIONAL_SCENARIOS,
    PRESSURE_SENSORS,
    VALIDATION_CHECKS,
    HydraulicSnapshot,
    LinkStatus,
    ScenarioSpec,
    ValidationLogRow,
)
from shared.units import ft_to_m
from sim.engine.mass_balance import MASS_BALANCE_TOL_M3S, mass_balance_error_m3s
from sim.engine.network import (
    CANONICAL_LINKS,
    CANONICAL_NODES,
    JUNCTIONS,
    PUMP_ID,
    TANK_ID,
    TANK_MAX_LEVEL_FT,
)

PRESSURE_TOL_M = 1e-6
TANK_TOL_M = 1e-3  # WNTR overshoots an emptying tank by ~1e-4 m (measured); 1 mm tolerance
STATE_TABLES = ("node_states", "link_states", "tank_states", "pump_states", "context")
_VALID_PUMP_STATUS = {s.value for s in LinkStatus}


def expected_steps(spec: ScenarioSpec) -> int:
    return spec.duration_s // spec.timestep_s + 1


def _check_converged(spec, tables, snapshots, converged):
    n = expected_steps(spec)
    got = len(snapshots) if snapshots is not None else 0
    ok = bool(converged) and got == n
    return ok, f"{got}/{n} snapshots" + ("" if converged else "; solver did not converge")


def _check_pressure(spec, tables, snapshots, converged):
    if spec.scenario_type not in OPERATIONAL_SCENARIOS:
        return True, "not enforced (leak scenario)"
    ns = tables["node_states"]
    p = ns.loc[ns["node_id"].isin(JUNCTIONS), "pressure_m"]
    worst = float(p.min())
    return worst >= -PRESSURE_TOL_M, f"min junction pressure {worst:.2f} m"


def _check_mass_balance(spec, tables, snapshots, converged):
    if not snapshots:
        return False, "no snapshots"
    worst = max(abs(mass_balance_error_m3s(s)) for s in snapshots)
    ok = worst <= MASS_BALANCE_TOL_M3S
    # value printed only on failure: below tolerance it is solver noise (keeps validation_log reproducible)
    return ok, f"max |imbalance| <= {MASS_BALANCE_TOL_M3S:g} m3/s" if ok else f"max |imbalance| {worst:.3e} m3/s"


def _check_tank(spec, tables, snapshots, converged):
    lv = tables["tank_states"]["level_m"].to_numpy(dtype=float)
    hi = ft_to_m(TANK_MAX_LEVEL_FT)
    ok = bool(np.all(lv >= -TANK_TOL_M) and np.all(lv <= hi + TANK_TOL_M))
    return ok, f"level range [{np.nanmin(lv):.2f}, {np.nanmax(lv):.2f}] m, max {hi:.2f} m"


def _check_elements(spec, tables, snapshots, converged):
    n = expected_steps(spec)
    want = {
        "node_states": ("node_id", set(CANONICAL_NODES)),
        "link_states": ("link_id", set(CANONICAL_LINKS)),
        "tank_states": ("tank_id", {TANK_ID}),
        "pump_states": ("pump_id", {PUMP_ID}),
        "sensors": ("sensor_id", set(PRESSURE_SENSORS) | set(FLOW_SENSORS)),
    }
    for name, (col, ids) in want.items():
        df = tables[name]
        if len(df) != n * len(ids) or set(df[col]) != ids or df["sim_time_s"].nunique() != n:
            return False, f"{name}: {len(df)} rows, ids {sorted(set(df[col]))}"
    if len(tables["context"]) != n:
        return False, f"context: {len(tables['context'])} rows"
    return True, f"{n} steps, all canonical elements"


def _check_nan(spec, tables, snapshots, converged):
    bad = []
    for name in STATE_TABLES:
        num = tables[name].select_dtypes(include="number")
        if bool(num.isna().to_numpy().any()) or not bool(np.isfinite(num.to_numpy(dtype=float)).all()):
            bad.append(name)
    if tables["sensors"]["true_value"].isna().any():
        bad.append("sensors.true_value")
    return not bad, ("NaN/inf in " + ", ".join(bad)) if bad else "no NaN"


def _check_pump(spec, tables, snapshots, converged):
    st = set(tables["pump_states"]["status"])
    ctx = set(tables["context"]["pump_status"].dropna().astype(int))
    ok = st <= _VALID_PUMP_STATUS and ctx <= {0, 1} and not tables["context"]["pump_status"].isna().any()
    return ok, f"pump status {sorted(st)}, context {sorted(ctx)}"


_CHECKS = {
    "converged": _check_converged,
    "no_negative_pressure_normal": _check_pressure,
    "mass_balance": _check_mass_balance,
    "tank_level_in_range": _check_tank,
    "all_canonical_elements_present": _check_elements,
    "no_nan": _check_nan,
    "pump_status_valid": _check_pump,
}


def failure_rows(spec: ScenarioSpec, detail: str) -> list[ValidationLogRow]:
    """Rows for a simulation that never produced results (solver exception)."""
    return [
        ValidationLogRow(
            simulation_id=spec.simulation_id,
            seed=spec.seed,
            check=c,
            passed=False,
            detail=detail if c == "converged" else "not evaluated: simulation failed",
            generator_version=spec.generator_version,
        )
        for c in VALIDATION_CHECKS
    ]


def validate_simulation(
    spec: ScenarioSpec,
    tables: dict[str, pd.DataFrame],
    snapshots: list[HydraulicSnapshot] | None = None,
    converged: bool = True,
) -> list[ValidationLogRow]:
    """Run every check in models.VALIDATION_CHECKS; one row per check, pass or fail."""
    rows = []
    for check in VALIDATION_CHECKS:
        try:
            passed, detail = _CHECKS[check](spec, tables, snapshots, converged)
        except Exception as exc:  # a malformed table is a validation failure, not a crash
            passed, detail = False, f"check raised {type(exc).__name__}: {exc}"
        rows.append(
            ValidationLogRow(
                simulation_id=spec.simulation_id,
                seed=spec.seed,
                check=check,
                passed=bool(passed),
                detail=detail,
                generator_version=spec.generator_version,
            )
        )
    return rows
