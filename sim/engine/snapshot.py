"""Map WNTR results to canonical HydraulicSnapshot (BACKBONE §7.4): `4_B`→`4`, `LK_*`→hidden.

Sign conventions (measured, WNTR 1.5): reservoir `demand` is negative (outflow); tank `demand`
is positive while the tank is filling, so `TankState.net_inflow_m3s = tank demand`.
`NodeState.base_demand_m3s` is the junction's expected demand at `t_s` (nominal base x diurnal
multiplier, taps included) when the model `wn` is given, else the nominal base demand.
"""

from __future__ import annotations

import math

from shared.contracts.models import (
    HiddenState,
    HydraulicSnapshot,
    LeakNodeState,
    LinkState,
    LinkStatus,
    NodeState,
    PumpState,
    TankState,
)
from shared.units import ft_to_m, gpm_to_m3s
from sim.engine.network import (
    CANONICAL_LINKS,
    CANONICAL_NODES,
    JUNCTIONS,
    NETWORK_ID,
    PIPES,
    PUMP_END,
    PUMP_ID,
    PUMP_START,
    TANK_DIAMETER_FT,
    TANK_ID,
    canonical_pipe_endpoints,
)

_STATUS = {0: LinkStatus.CLOSED, 1: LinkStatus.OPEN, 2: LinkStatus.ACTIVE}
_LEAK_EPS = 0.0


def _status(code) -> LinkStatus:
    return _STATUS.get(int(code), LinkStatus.OPEN)


def _expected_demand(wn, node_id: str, t_s: int) -> float:
    if wn is None:
        return gpm_to_m3s(JUNCTIONS[node_id][1])
    node = wn.get_node(node_id)
    return float(sum(d.at(t_s) for d in node.demand_timeseries_list))


def to_snapshot(results, t_s: int, network_id: str = NETWORK_ID, wn=None) -> HydraulicSnapshot:
    """Canonical snapshot at time `t_s`. Canonical link reports the UPSTREAM half's flow (§7.4)."""
    nd, lk = results.node, results.link
    head, press, dem = nd["head"].loc[t_s], nd["pressure"].loc[t_s], nd["demand"].loc[t_s]
    leak = nd["leak_demand"].loc[t_s]
    flow, vel, stat = lk["flowrate"].loc[t_s], lk["velocity"].loc[t_s], lk["status"].loc[t_s]

    nodes = {}
    for n in CANONICAL_NODES:
        is_junction = n in JUNCTIONS
        nodes[n] = NodeState(
            pressure_m=float(press[n]),
            head_m=float(head[n]),
            demand_m3s=float(dem[n]),
            base_demand_m3s=_expected_demand(wn, n, t_s) if is_junction else 0.0,
            leak_m3s=float(leak[n]) if is_junction else 0.0,
        )

    links = {}
    for p in CANONICAL_LINKS:
        if p == PUMP_ID:
            links[p] = LinkState(
                flow_m3s=float(flow[p]),
                velocity_ms=0.0,
                headloss_m=-float(head[PUMP_END] - head[PUMP_START]),
                status=_status(stat[p]),
            )
        else:
            s, e = canonical_pipe_endpoints(p)
            links[p] = LinkState(
                flow_m3s=float(flow[p]),
                velocity_ms=float(vel[p]),
                headloss_m=float(head[s] - head[e]),
                status=_status(stat[p]),
            )

    pumps = {
        PUMP_ID: PumpState(
            flow_m3s=float(flow[PUMP_ID]),
            head_gain_m=float(head[PUMP_END] - head[PUMP_START]),
            status=_status(stat[PUMP_ID]),
        )
    }
    level = float(press[TANK_ID])
    diameter = ft_to_m(TANK_DIAMETER_FT)
    tanks = {
        TANK_ID: TankState(
            level_m=level,
            head_m=float(head[TANK_ID]),
            volume_m3=math.pi * diameter**2 / 4.0 * level,
            net_inflow_m3s=float(dem[TANK_ID]),
        )
    }

    leak_nodes = {
        str(n): LeakNodeState(leak_m3s=float(leak[n]))
        for n in leak.index
        if str(n).startswith("LK_") and leak[n] > _LEAK_EPS
    }
    return HydraulicSnapshot(
        network_id=network_id,
        sim_time_s=int(t_s),
        converged=True,
        nodes=nodes,
        links=links,
        tanks=tanks,
        pumps=pumps,
        hidden=HiddenState(leak_nodes=leak_nodes),
    )


def to_snapshots(results, network_id: str = NETWORK_ID, wn=None) -> list[HydraulicSnapshot]:
    """Snapshots for every timestep in `results`."""
    return [to_snapshot(results, int(t), network_id, wn) for t in results.node["pressure"].index]


__all__ = ["PIPES", "to_snapshot", "to_snapshots"]
