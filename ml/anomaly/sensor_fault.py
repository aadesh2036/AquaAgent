"""SENSOR_FAULT rule (BACKBONE §9.3) — T3, needs ds2.

Implementation: docs/modules/05_ANOMALY_LOCALISATION.md
"""

from __future__ import annotations

from shared.contracts.models import ResidualFrame


def is_sensor_fault(history: list[ResidualFrame], step_bound_m: float, stuck_var_eps: float) -> str | None:
    """Return the faulty sensor_id or None."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/05_ANOMALY_LOCALISATION.md")
