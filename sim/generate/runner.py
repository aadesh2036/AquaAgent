"""Run simulations and shards (BACKBONE §7.5, §8.1, §8.4, §8.6).

`run_simulation(spec, network_cfg)` = build -> demand/ops/faults -> 24 h EPS at 300 s (289 rows) ->
canonical snapshots -> §7.5 tables (state layer SI, observation layer m / L/s) -> validation.
Solver exceptions never escape: they become `ok=False` plus validation rows.

Implementation: docs/modules/02_DATA_GENERATION.md
"""

from __future__ import annotations

import json
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import wntr
import yaml

from shared.contracts.models import (
    FLOW_SENSORS,
    PRESSURE_SENSORS,
    SCENARIO_IS_ANOMALOUS,
    TABLE_COLUMNS,
    FaultType,
    HydraulicSnapshot,
    LocationKind,
    NetworkConfig,
    ScenarioSpec,
    SensorLayout,
    SeverityBucket,
    ValidationLogRow,
)
from shared.units import m3s_to_lps, pump_status_to_int, time_of_day_s
from sim.engine import network as net
from sim.engine.leaks import add_junction_leak, add_pipe_leak
from sim.engine.snapshot import to_snapshots
from sim.generate import writer
from sim.generate.noise import apply_noise_and_faults
from sim.generate.validation import failure_rows, validate_simulation
from sim.scenarios.demand import hourly_multipliers
from sim.scenarios.sampler import derive_seed, make_rng, pipe_split_positions, plan_dataset

VALID_FRACTION_MIN = 0.95
_FALLBACK_LAYOUT = {
    "sensor_layout_id": "sensors_default_v1",
    "pressure": [{"sensor_id": "S1", "node_id": "2"}, {"sensor_id": "S2", "node_id": "4"}, {"sensor_id": "S3", "node_id": "6"}],
    "flow": [{"sensor_id": "F1", "link_id": "3"}, {"sensor_id": "F2", "link_id": "6"}],
    "context": ["tank_level_m", "pump_status", "pump_flow_lps", "reservoir_head_m", "time_of_day_s"],
}  # fmt: skip


@dataclass
class SimResult:
    tables: dict[str, pd.DataFrame]
    validation_rows: list[ValidationLogRow]
    ok: bool
    detail: str = ""
    extra: dict = field(default_factory=dict)


def load_sensor_layout(layout_id: str) -> SensorLayout:
    p = net.REPO_ROOT / "config" / "sensors" / f"{layout_id}.json"
    data = json.loads(p.read_text()) if p.exists() else _FALLBACK_LAYOUT
    return SensorLayout.model_validate(data)


def hop_distances(network_cfg: NetworkConfig, sensor_nodes: list[str]) -> dict[str, int]:
    """BFS hop count from the nearest pressure-sensor node on the canonical graph (pipes + pump)."""
    adj: dict[str, set[str]] = {n.node_id: set() for n in network_cfg.nodes}
    for lk in network_cfg.links:
        adj[lk.start_node].add(lk.end_node)
        adj[lk.end_node].add(lk.start_node)
    dist = {n: 0 for n in sensor_nodes}
    q = deque(sensor_nodes)
    while q:
        u = q.popleft()
        for v in sorted(adj[u]):
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


# --------------------------------------------------------------------------- simulation


def _run_to(wn, t_s: int):
    wn.options.time.duration = t_s
    return wntr.sim.WNTRSimulator(wn).run_sim()


def simulate(spec: ScenarioSpec, network_id: str | None = None) -> list[HydraulicSnapshot]:
    """Build the model for `spec`, run the 24 h EPS and return canonical snapshots (289)."""
    prof = spec.demand_profile
    positions = pipe_split_positions(spec.seed)
    for f in spec.faults:
        if f.location_kind == LocationKind.PIPE and f.position is not None:
            positions[f.location_id] = f.position  # the spec is the source of truth
    wn = net.build_network(
        network_id or spec.network_id,
        pipe_split_pos=positions,
        demand_profile=prof,
        duration_s=spec.duration_s,
        tank_init_level_m=spec.operations.tank_init_level_m,
        reservoir_head_offset_m=spec.operations.reservoir_head_offset_m,
        pump_speed=spec.operations.pump_speed,
    )
    wn.get_pattern(net.DIURNAL_PATTERN).multipliers = hourly_multipliers(prof, make_rng(derive_seed(spec.seed, "demand")))
    shift = None
    for f in spec.faults:
        if f.fault_type in (FaultType.LEAK, FaultType.BURST):
            if f.location_kind == LocationKind.PIPE:
                add_pipe_leak(wn, f.location_id, f.leak_area_m2, f.start_s, f.end_s, f.discharge_coeff)
            else:
                add_junction_leak(wn, f.location_id, f.leak_area_m2, f.start_s, f.end_s, f.discharge_coeff)
        elif f.fault_type == FaultType.DEMAND_SHIFT:
            shift = f
        else:
            raise ValueError(f"unsupported fault type {f.fault_type} in ds1")

    if shift is None:
        return to_snapshots(_run_to(wn, spec.duration_s), spec.network_id, wn)

    # DEMAND_SHIFT: stop one step before t_f, scale the base demands, continue (BACKBONE §6.3 stop/restart)
    p = shift.params
    snaps = to_snapshots(_run_to(wn, shift.start_s - spec.timestep_s), spec.network_id, wn)
    for node, mult in ((p["node_up"], p["mult_up"]), (p["node_down"], p["mult_down"])):
        base = [d for d in wn.get_node(node).demand_timeseries_list if d.category != net.TAP_DEMAND_CATEGORY][0]
        base.base_value = base.base_value * mult
    return snaps + to_snapshots(_run_to(wn, spec.duration_s), spec.network_id, wn)


def leak_metrics(snaps: list[HydraulicSnapshot]) -> tuple[float, float]:
    """(peak total leak flow m3/s, mean total junction demand m3/s) over the episode."""
    leak = np.array(
        [
            sum(n.leak_m3s for n in s.nodes.values()) + sum(v.leak_m3s for v in (s.hidden.leak_nodes.values() if s.hidden else []))
            for s in snaps
        ]
    )
    demand = np.array([sum(n.demand_m3s for k, n in s.nodes.items() if k in net.JUNCTIONS) for s in snaps])
    return float(leak.max()), float(demand.mean())


def severity_bucket(peak_m3s: float, mean_demand_m3s: float) -> SeverityBucket:
    pct = 100.0 * peak_m3s / mean_demand_m3s
    if pct < 5.0:
        return SeverityBucket.LT5
    if pct < 15.0:
        return SeverityBucket.B5_15
    if pct < 25.0:
        return SeverityBucket.B15_25
    return SeverityBucket.GT25


# --------------------------------------------------------------------------- tables

# WNTR's C++ evaluator orders its Jacobian by Var* pointer (std::map<Var*, ...>), so results jitter
# by <= 1.1e-13 (m) / 5e-16 (m3/s) between runs/processes (measured). Values are therefore rounded
# to a fixed physical resolution so the Parquet bytes are reproducible: a value only flips if it
# lies within the jitter of a rounding boundary (~1e-4 expected flips per sim; see sim/README.md).
DECIMALS = {"_m": 4, "_m3s": 7, "_ms": 5, "_m3": 3, "_lps": 4}


def _decimals(col: str) -> int | None:
    for suffix, d in DECIMALS.items():
        if col.endswith(suffix):
            return d
    return None


def quantize(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        d = _decimals(col)
        if d is not None and df[col].dtype.kind == "f":
            df[col] = df[col].round(d)
    return df


def build_tables(spec: ScenarioSpec, snaps: list[HydraulicSnapshot], network_cfg: NetworkConfig) -> dict[str, pd.DataFrame]:
    """§7.5 tables (without scenarios) with exact TABLE_COLUMNS, rows ordered (sim, time, id)."""
    sid = spec.simulation_id
    layout = load_sensor_layout(spec.sensor_layout_id)
    sensor_nodes = [s.node_id for s in layout.pressure]
    hops = hop_distances(network_cfg, sensor_nodes)
    ntype = {n.node_id: n.node_type.value for n in network_cfg.nodes}
    ltype = {k.link_id: k.link_type.value for k in network_cfg.links}

    node_rows, link_rows, tank_rows, pump_rows, ctx_rows = [], [], [], [], []
    for s in snaps:
        t = s.sim_time_s
        for nid, n in s.nodes.items():
            node_rows.append(
                (sid, t, nid, ntype[nid], n.pressure_m, n.head_m, n.demand_m3s, n.base_demand_m3s, n.leak_m3s,
                 nid in sensor_nodes, hops[nid])
            )  # fmt: skip
        for lid, lk in s.links.items():
            link_rows.append((sid, t, lid, ltype[lid], lk.flow_m3s, lk.velocity_ms, lk.headloss_m, lk.status.value))
        for tid, tk in s.tanks.items():
            tank_rows.append((sid, t, tid, tk.level_m, tk.head_m, tk.volume_m3, tk.net_inflow_m3s))
        for pid, pu in s.pumps.items():
            pump_rows.append((sid, t, pid, pu.flow_m3s, pu.head_gain_m, pu.status.value))
        pump = s.pumps[net.PUMP_ID]
        ctx_rows.append(
            (sid, t, time_of_day_s(t), s.tanks[net.TANK_ID].level_m, pump_status_to_int(pump.status.value),
             m3s_to_lps(pump.flow_m3s), s.nodes[net.RESERVOIR_ID].head_m)
        )  # fmt: skip

    def frame(name, rows):
        df = pd.DataFrame(rows, columns=list(TABLE_COLUMNS[name]))
        key = [c for c in df.columns if c in ("sim_time_s", "node_id", "link_id", "tank_id", "pump_id")]
        return quantize(df.sort_values(["simulation_id", *key], kind="stable").reset_index(drop=True))

    # sensors: truth in observation units, noise only on measured_value (§8.3)
    times = np.array([s.sim_time_s for s in snaps])
    rng = make_rng(derive_seed(spec.seed, "noise"))
    sensor_rows = []
    specs = [(d.sensor_id, "node", d.node_id, "pressure_m") for d in layout.pressure]
    specs += [(d.sensor_id, "link", d.link_id, "flow_lps") for d in layout.flow]
    assert [x[0] for x in specs] == [*PRESSURE_SENSORS, *FLOW_SENSORS]
    for sensor_id, kind, src, meas in specs:
        if kind == "node":
            truth = np.array([s.nodes[src].pressure_m for s in snaps])
        else:
            truth = np.array([m3s_to_lps(s.links[src].flow_m3s) for s in snaps])
        truth = np.round(truth, DECIMALS["_m"])  # same resolution as the state tables (see DECIMALS)
        measured, fkind = apply_noise_and_faults(
            truth, meas, spec.noise, [f for f in spec.sensor_faults if f.sensor_id == sensor_id], times, rng
        )
        measured = np.round(measured, DECIMALS["_m"])
        for i, t in enumerate(times):
            sensor_rows.append((sid, int(t), sensor_id, kind, src, meas, float(truth[i]), float(measured[i]), fkind[i]))

    return {
        "node_states": frame("node_states", node_rows),
        "link_states": frame("link_states", link_rows),
        "tank_states": frame("tank_states", tank_rows),
        "pump_states": frame("pump_states", pump_rows),
        "sensors": frame("sensors", sensor_rows),
        "context": frame("context", ctx_rows),
    }


def scenario_row(spec: ScenarioSpec, snaps: list[HydraulicSnapshot], network_cfg: NetworkConfig) -> dict:
    """The `scenarios` row (columns of TABLE_COLUMNS['scenarios'] minus `split`, completed at merge)."""
    f = spec.faults[0] if spec.faults else None
    peak = bucket = None
    if f is not None and f.fault_type in (FaultType.LEAK, FaultType.BURST):
        peak, mean_demand = leak_metrics(snaps)
        bucket = severity_bucket(peak, mean_demand).value
        peak = round(peak, DECIMALS["_m3s"])
    zone = None
    if f is not None and f.location_id is not None:
        if f.location_kind == LocationKind.PIPE:
            zone = next(k.zone_id for k in network_cfg.links if k.link_id == f.location_id)
        else:
            zone = next(n.zone_id for n in network_cfg.nodes if n.node_id == f.location_id)
    return {
        "simulation_id": spec.simulation_id,
        "dataset_version": spec.simulation_id.split("_")[1],
        "network_id": spec.network_id,
        "sensor_layout_id": spec.sensor_layout_id,
        "scenario_type": spec.scenario_type.value,
        "is_anomalous": SCENARIO_IS_ANOMALOUS[spec.scenario_type],
        "has_sensor_fault": bool(spec.sensor_faults),
        "fault_type": f.fault_type.value if f else None,
        "location_kind": f.location_kind.value if f and f.location_kind else None,
        "location_id": f.location_id if f else None,
        "zone_id": zone,
        "position": f.position if f else None,
        "leak_area_m2": f.leak_area_m2 if f else None,
        "fault_start_s": f.start_s if f else None,
        "fault_end_s": f.end_s if f else None,
        "realised_leak_peak_m3s": peak,
        "severity_bucket": bucket,
        "seed": spec.seed,
        "config_hash": spec.config_hash,
        "generator_version": spec.generator_version,
        "spec_json": spec.model_dump_json(),
        "valid": True,
    }


def run_simulation(spec: ScenarioSpec, network_cfg: NetworkConfig | None = None) -> SimResult:
    """Simulate + tabulate + validate one spec. Never raises on solver/WNTR errors."""
    network_cfg = network_cfg or net.network_config(spec.network_id)
    try:
        snaps = simulate(spec)
        tables = build_tables(spec, snaps, network_cfg)
        row = scenario_row(spec, snaps, network_cfg)
    except Exception as exc:  # WNTR raises assorted types on non-convergence
        detail = f"{type(exc).__name__}: {exc}"
        return SimResult({}, failure_rows(spec, detail[:300]), False, detail)
    rows = validate_simulation(spec, tables, snaps)
    ok = all(r.passed for r in rows)
    if not ok:
        return SimResult({}, rows, False, "; ".join(f"{r.check}: {r.detail}" for r in rows if not r.passed))
    tables["scenarios"] = pd.DataFrame([row])
    return SimResult(tables, rows, True)


# --------------------------------------------------------------------------- shard

_TABLE_ORDER = ("scenarios", "node_states", "link_states", "tank_states", "pump_states", "sensors", "context")


def load_config(config_path: str) -> dict:
    return yaml.safe_load(Path(config_path).read_text())


def run_shard(
    config_path: str, shard: int, num_shards: int, out_uri: str, limit: int | None = None, progress_every: int = 50
) -> dict:
    """Simulate specs where `sim_index % num_shards == shard`; write one Parquet per table to `out_uri`."""
    if not 0 <= shard < num_shards:
        raise ValueError("shard must be in [0, num_shards)")
    cfg = load_config(config_path)
    network_cfg = net.network_config(cfg["network_id"])
    specs = [s for i, s in enumerate(plan_dataset(cfg)) if i % num_shards == shard]
    if limit is not None:
        specs = specs[:limit]
    acc: dict[str, list[pd.DataFrame]] = {t: [] for t in _TABLE_ORDER}
    vlog: list[dict] = []
    n_ok = 0
    t0 = time.perf_counter()
    for k, spec in enumerate(specs, 1):
        res = run_simulation(spec, network_cfg)
        vlog += [r.model_dump() for r in res.validation_rows]
        if res.ok:
            n_ok += 1
            for name in _TABLE_ORDER:
                acc[name].append(res.tables[name])
        else:
            print(f"[shard {shard}] {spec.simulation_id} EXCLUDED: {res.detail}", file=sys.stderr)
        if k % progress_every == 0 or k == len(specs):
            el = time.perf_counter() - t0
            print(f"[shard {shard}] {k}/{len(specs)} sims, {n_ok} valid, {el:.1f}s ({el / k:.2f}s/sim)", flush=True)
    tables = {}
    for name in _TABLE_ORDER:
        parts = acc[name]
        if parts:
            tables[name] = writer.concat(parts)
        else:
            cols = [c for c in TABLE_COLUMNS[name] if not (name == "scenarios" and c == "split")]
            tables[name] = pd.DataFrame(columns=cols)
    tables["scenarios"] = tables["scenarios"][[c for c in TABLE_COLUMNS["scenarios"] if c != "split"]]
    tables["validation_log"] = pd.DataFrame(vlog, columns=list(TABLE_COLUMNS["validation_log"]))
    writer.write_shard(tables, out_uri, shard)
    elapsed = time.perf_counter() - t0
    return {
        "shard": shard,
        "n_requested": len(specs),
        "n_valid": n_ok,
        "n_failed": len(specs) - n_ok,
        "elapsed_s": elapsed,
        "s_per_sim": elapsed / max(len(specs), 1),
        "valid_fraction": n_ok / len(specs) if specs else 0.0,
    }
