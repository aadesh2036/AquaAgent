"""The ONLY HydraulicSnapshot -> NetworkView path (BACKBONE §7.14.1, §11).

Rules: units via shared.units; `snapshot.hidden`, LK_* nodes and hidden events are never read;
`visual_fault` comes only from user actions. Node status bands: low < 20 m, critical < 10 m.
Reservoir/tank `demand_lps` keeps the sign of the snapshot demand (negative = water leaving the
node into the network), junctions are consumer demand.
"""

from __future__ import annotations

from api.session.store import SessionState
from shared import units
from shared.contracts.models import (
    NetworkStatus,
    NetworkTopology,
    NetworkView,
    NodeType,
    NodeUiStatus,
    SensorLayout,
    ViewChallenge,
    ViewLink,
    ViewNode,
    ViewPump,
    ViewTank,
    ViewTap,
    ViewValve,
    VisualFault,
)

LOW_PRESSURE_M = 20.0
CRITICAL_PRESSURE_M = 10.0
DIRECTION_EPS_M3S = 1e-6


def node_status(pressure_m: float) -> NodeUiStatus:
    if pressure_m < CRITICAL_PRESSURE_M:
        return NodeUiStatus.CRITICAL
    if pressure_m < LOW_PRESSURE_M:
        return NodeUiStatus.LOW
    return NodeUiStatus.OK


def to_network_view(
    snapshot,
    state: SessionState,
    topology: NetworkTopology,
    layout: SensorLayout,
    tank_max_level_m: float,
) -> NetworkView:
    types = {n.node_id: n.node_type for n in topology.nodes}
    sensor_of = {s.node_id: s.sensor_id for s in layout.pressure}

    nodes: dict[str, ViewNode] = {}
    for nid, ns in snapshot.nodes.items():
        if nid not in types:  # never expose anything outside the canonical network (e.g. LK_*)
            continue
        ntype = types[nid]
        status = node_status(ns.pressure_m) if ntype == NodeType.JUNCTION else NodeUiStatus.OK
        nodes[nid] = ViewNode(
            pressure_m=ns.pressure_m,
            head_m=ns.head_m,
            demand_lps=units.m3s_to_lps(ns.demand_m3s),
            is_sensor=nid in sensor_of,
            sensor_id=sensor_of.get(nid),
            status=status,
        )

    link_ids = {lk.link_id for lk in topology.links}
    links: dict[str, ViewLink] = {}
    for lid, ls in snapshot.links.items():
        if lid not in link_ids:
            continue
        q = ls.flow_m3s
        direction = 0 if abs(q) < DIRECTION_EPS_M3S else (1 if q > 0 else -1)
        links[lid] = ViewLink(
            flow_lps=abs(units.m3s_to_lps(q)),
            velocity_ms=abs(ls.velocity_ms),
            status=ls.status,
            direction=direction,
            visual_fault=state.visual_faults.get(lid, VisualFault.NONE),
        )

    tank_id, ts = next(iter(snapshot.tanks.items()))
    pump_id, ps = next(iter(snapshot.pumps.items()))
    taps = {
        t.tap_id: ViewTap(
            open=state.taps.get(t.tap_id, False),
            demand_lps=units.m3s_to_lps(snapshot.nodes[t.node_id].demand_m3s),
        )
        for t in topology.taps
    }
    valves = {v.valve_id: ViewValve(open=state.valves.get(v.valve_id, True)) for v in topology.valves}

    return NetworkView(
        session_id=state.sim_session_id,
        sim_time_s=snapshot.sim_time_s,
        clock=units.clock_label(snapshot.sim_time_s),
        speed=state.speed,
        nodes=nodes,
        links=links,
        tank=ViewTank(
            tank_id=tank_id,
            level_m=ts.level_m,
            level_pct=units.level_pct(ts.level_m, tank_max_level_m),
        ),
        pump=ViewPump(
            pump_id=pump_id,
            flow_lps=units.m3s_to_lps(ps.flow_m3s),
            status=units.pump_status_to_ui(ps.status.value),
        ),
        taps=taps,
        valves=valves,
        network_status=NetworkStatus.NORMAL,
        challenge=ViewChallenge(active=False),
        events=state.events.public_events(limit=20),
    )
