"""HydraulicSnapshot → observation step (BACKBONE §7.8, §11): the ONE place truth becomes sensor readings.

Used by the api's ``SensorWindowBuffer`` (live) and by ``ml.localisation.signatures`` (offline signatures),
so both see exactly the same observation layer. Only the sensor-layout pressures/flows and the SCADA context
are read; nothing else from the snapshot leaves this function. Noise = the ds1 model (§8.3).
"""

from __future__ import annotations

import numpy as np

from shared import units
from shared.contracts.models import HydraulicSnapshot, SensorLayout, WindowContext, WindowStep

PRESSURE_SIGMA_M = 0.05
FLOW_SIGMA_LPS = 0.10
RESERVOIR_NODE = "1"


def snapshot_to_step(
    snap: HydraulicSnapshot, layout: SensorLayout, rng: np.random.Generator | None = None
) -> WindowStep:
    """Sensor + context values for one snapshot (observation units m, L/s), with optional sensor noise."""

    def noisy(v: float, sigma: float) -> float:
        return round(v + (float(rng.normal(0.0, sigma)) if rng is not None else 0.0), 4)

    pressure = {
        s.sensor_id: noisy(snap.nodes[s.node_id].pressure_m, PRESSURE_SIGMA_M) for s in layout.pressure
    }
    flow = {
        f.sensor_id: noisy(units.m3s_to_lps(snap.links[f.link_id].flow_m3s), FLOW_SIGMA_LPS)
        for f in layout.flow
    }
    tank = next(iter(snap.tanks.values()))
    pump = next(iter(snap.pumps.values()))
    ctx = WindowContext(
        tank_level_m=round(tank.level_m, 4),
        pump_status=units.pump_status_to_int(pump.status.value),
        pump_flow_lps=round(units.m3s_to_lps(pump.flow_m3s), 4),
        reservoir_head_m=round(snap.nodes[RESERVOIR_NODE].head_m, 4),
        time_of_day_s=units.time_of_day_s(snap.sim_time_s),
    )
    return WindowStep(sim_time_s=snap.sim_time_s, pressure_m=pressure, flow_lps=flow, context=ctx)
