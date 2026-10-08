"""Build `net_epa_tutorial_v1` in WNTR (BACKBONE §6, §7.1).

The canonical spec lives here in source units (ft / in / gpm) and is converted to SI ONLY
through `shared.units`. Later steps (leaks, snapshots, config export) import these constants.

Implementation: docs/modules/01_SIMULATION_ENGINE.md
"""

from __future__ import annotations

import math
from pathlib import Path

import wntr

from shared.contracts.models import (
    DemandProfile,
    HydraulicsConfig,
    LinkConfig,
    LinkStatus,
    LinkType,
    NetworkConfig,
    NodeConfig,
    NodeType,
    TapDef,
    ValveDef,
    Zone,
)
from shared.units import ft_to_m, gpm_to_m3s, in_to_m, lps_to_m3s

# --- canonical specification (source units) ---------------------------------------------------

NETWORK_ID = "net_epa_tutorial_v1"

RESERVOIR_ID = "1"
RESERVOIR_HEAD_FT = 700.0
# id -> (elevation ft, base demand gpm)
JUNCTIONS: dict[str, tuple[float, float]] = {
    "2": (700.0, 0.0),
    "3": (710.0, 150.0),
    "4": (700.0, 150.0),
    "5": (650.0, 200.0),
    "6": (700.0, 150.0),
    "7": (700.0, 0.0),
}
TANK_ID = "8"
TANK_ELEVATION_FT = 830.0
TANK_INIT_LEVEL_M = 1.07  # open decision D3, already metres
TANK_MIN_LEVEL_FT = 0.0
TANK_MAX_LEVEL_FT = 20.0
TANK_DIAMETER_FT = 60.0

HW_ROUGHNESS = 100.0
# id -> (start, end, length ft, diameter in)
PIPES: dict[str, tuple[str, str, float, float]] = {
    "1": ("2", "3", 3000.0, 14.0),
    "2": ("3", "7", 5000.0, 12.0),
    "3": ("3", "4", 5000.0, 8.0),
    "4": ("4", "6", 5000.0, 8.0),
    "5": ("7", "6", 5000.0, 8.0),
    "6": ("7", "8", 7000.0, 10.0),
    "7": ("4", "5", 5000.0, 6.0),
    "8": ("5", "6", 7000.0, 6.0),
}
PUMP_ID = "9"
PUMP_START, PUMP_END = "1", "2"
PUMP_FLOW_GPM = 600.0
PUMP_HEAD_FT = 150.0

ZONES = {"Z1": "Supply & Commercial", "Z2": "West & Valley", "Z3": "East & Storage"}
NODE_ZONE = {
    "1": "Z1", "2": "Z1", "3": "Z1",
    "4": "Z2", "5": "Z2",
    "6": "Z3", "7": "Z3", "8": "Z3",
}  # fmt: skip
LINK_ZONE = {
    "1": "Z1", "2": "Z1", "9": "Z1",
    "3": "Z2", "4": "Z2", "7": "Z2", "8": "Z2",
    "5": "Z3", "6": "Z3",
}  # fmt: skip

# UI coordinates (Fig 2.1; x right, y down, arbitrary units)
COORDS: dict[str, tuple[float, float]] = {
    "1": (15.0, 35.0),
    "2": (90.0, 35.0),
    "3": (143.0, 35.0),
    "7": (205.0, 35.0),
    "8": (265.0, 35.0),
    "4": (143.0, 100.0),
    "6": (205.0, 100.0),
    "5": (143.0, 165.0),
}
UI_LABELS = {
    "1": "Source",
    "2": "Pump discharge header",
    "3": "Commercial district",
    "4": "West residential",
    "5": "Valley consumers",
    "6": "East residential",
    "7": "Loop tie point",
    "8": "Elevated storage",
}

TAPS = {"T1": "3", "T2": "4", "T3": "6"}  # tap id -> junction
VALVES = {"V1": "7"}  # valve id -> pipe (implemented as pipe_status)
TAP_EXTRA_DEMAND_M3S = lps_to_m3s(5.0)  # extra demand while a tap is open (step 5)
TAP_DEMAND_CATEGORY = "tap"

CANONICAL_NODES = [str(i) for i in range(1, 9)]
CANONICAL_LINKS = [str(i) for i in range(1, 10)]
LEAK_PIPES = [str(i) for i in range(1, 9)]

TIMESTEP_S = 300
REQUIRED_PRESSURE_M = 20.0
MINIMUM_PRESSURE_M = 0.0
PATTERN_TIMESTEP_S = 3600
DIURNAL_PATTERN = "diurnal"

# BACKBONE §7.2 example values (noise_sigma is ignored here; noise belongs to module 02)
DEFAULT_DEMAND_PROFILE = DemandProfile(
    profile_id="diurnal_default",
    night_min=0.35,
    morning_peak_mult=1.45,
    morning_peak_h=7.5,
    evening_peak_mult=1.60,
    evening_peak_h=19.0,
    noise_sigma=0.03,
)
_PEAK_SIGMA_H = 2.0


def _circ_dist_h(a: float, b: float) -> float:
    d = abs(a - b) % 24.0
    return min(d, 24.0 - d)


def diurnal_multipliers(profile: DemandProfile | None = None) -> list[float]:
    """24 deterministic hourly demand multipliers (no noise).

    Shape = `night_min` floor plus two Gaussian bumps (sigma 2 h, wrap-around on 24 h) whose
    heights reach `*_peak_mult` at `*_peak_h`; scaled by `global_mult` if set.
    """
    p = profile or DEFAULT_DEMAND_PROFILE
    out = []
    for h in range(24):
        v = p.night_min
        for mult, centre in (
            (p.morning_peak_mult, p.morning_peak_h),
            (p.evening_peak_mult, p.evening_peak_h),
        ):
            d = _circ_dist_h(float(h), centre)
            v = max(v, p.night_min + (mult - p.night_min) * math.exp(-0.5 * (d / _PEAK_SIGMA_H) ** 2))
        out.append(v * (p.global_mult if p.global_mult is not None else 1.0))
    return out


def canonical_pipe_endpoints(pipe_id: str) -> tuple[str, str]:
    """(start, end) node ids of a canonical pipe, from `PIPES`."""
    start, end, _, _ = PIPES[pipe_id]
    return start, end


def build_network(
    network_id: str = NETWORK_ID,
    *,
    pipe_split_pos: float | dict[str, float] | None = 0.5,
    demand_profile: DemandProfile | None = None,
    duration_s: int = 86400,
    tank_init_level_m: float = TANK_INIT_LEVEL_M,
    reservoir_head_offset_m: float = 0.0,
    pump_speed: float = 1.0,
) -> wntr.network.WaterNetworkModel:
    """Build the canonical network programmatically from the constants above.

    Pre-splitting (BACKBONE §6.3): each pipe `p` in LEAK_PIPES is split with
    `wntr.morph.split_pipe(..., add_pipe_at_end=True)`. The canonical id `p` stays the UPSTREAM
    half (original start node -> `LK_p`); the new `p_B` is the downstream half (`LK_p` -> original
    end). `LK_p` is a zero-demand junction, so healthy hydraulics are unchanged.

    Each tap junction (3, 4, 6) carries a second demand entry with base 0.0, constant pattern "1" (flat 1.0) and
    category `tap` (TAP_DEMAND_CATEGORY); find it with
    `[d for d in junction.demand_timeseries_list if d.category == "tap"]`.
    """
    if network_id != NETWORK_ID:
        raise ValueError(f"unknown network_id {network_id!r}")
    profile = demand_profile or DEFAULT_DEMAND_PROFILE

    wn = wntr.network.WaterNetworkModel()
    opts = wn.options
    opts.hydraulic.headloss = "H-W"
    opts.hydraulic.demand_model = "PDD"
    opts.hydraulic.required_pressure = REQUIRED_PRESSURE_M
    opts.hydraulic.minimum_pressure = MINIMUM_PRESSURE_M
    opts.time.hydraulic_timestep = TIMESTEP_S
    opts.time.report_timestep = TIMESTEP_S
    opts.time.pattern_timestep = PATTERN_TIMESTEP_S
    opts.time.duration = duration_s

    wn.add_pattern(DIURNAL_PATTERN, diurnal_multipliers(profile))
    # WNTR's default demand pattern name is "1"; define it as constant 1.0 so demand entries
    # created without a pattern (the tap entries) are explicitly flat.
    wn.add_pattern("1", [1.0])

    wn.add_reservoir(
        RESERVOIR_ID,
        base_head=ft_to_m(RESERVOIR_HEAD_FT) + reservoir_head_offset_m,
        coordinates=COORDS[RESERVOIR_ID],
    )
    tap_junctions = set(TAPS.values())
    for jid, (elev_ft, gpm) in JUNCTIONS.items():
        base = gpm_to_m3s(gpm) * profile.node_multipliers.get(jid, 1.0)
        wn.add_junction(
            jid,
            base_demand=base,
            demand_pattern=DIURNAL_PATTERN,
            elevation=ft_to_m(elev_ft),
            coordinates=COORDS[jid],
        )
        if jid in tap_junctions:
            wn.get_node(jid).add_demand(0.0, None, TAP_DEMAND_CATEGORY)
    wn.add_tank(
        TANK_ID,
        elevation=ft_to_m(TANK_ELEVATION_FT),
        init_level=tank_init_level_m,
        min_level=ft_to_m(TANK_MIN_LEVEL_FT),
        max_level=ft_to_m(TANK_MAX_LEVEL_FT),
        diameter=ft_to_m(TANK_DIAMETER_FT),
        coordinates=COORDS[TANK_ID],
    )
    for pid, (start, end, length_ft, diam_in) in PIPES.items():
        wn.add_pipe(
            pid, start, end, length=ft_to_m(length_ft), diameter=in_to_m(diam_in), roughness=HW_ROUGHNESS
        )
    wn.add_curve("1", "HEAD", [(gpm_to_m3s(PUMP_FLOW_GPM), ft_to_m(PUMP_HEAD_FT))])
    wn.add_pump(PUMP_ID, PUMP_START, PUMP_END, pump_type="HEAD", pump_parameter="1")
    wn.get_link(PUMP_ID).speed_timeseries.base_value = pump_speed

    if pipe_split_pos is not None:
        for p in LEAK_PIPES:
            pos = pipe_split_pos[p] if isinstance(pipe_split_pos, dict) else pipe_split_pos
            wn = wntr.morph.split_pipe(wn, p, f"{p}_B", f"LK_{p}", split_at_point=pos)
            s, e = canonical_pipe_endpoints(p)
            (x0, y0), (x1, y1) = COORDS[s], COORDS[e]
            wn.get_node(f"LK_{p}").coordinates = (x0 + pos * (x1 - x0), y0 + pos * (y1 - y0))
    return wn


def network_config(network_id: str = NETWORK_ID) -> NetworkConfig:
    """NetworkConfig (§7.1) built purely from the module constants (no WNTR)."""
    if network_id != NETWORK_ID:
        raise ValueError(f"unknown network_id {network_id!r}")

    def node(nid: str, ntype: NodeType, elev_m: float, demand: float | None) -> NodeConfig:
        x, y = COORDS[nid]
        return NodeConfig(
            node_id=nid,
            node_type=ntype,
            elevation_m=elev_m,
            base_demand_m3s=demand,
            x=x,
            y=y,
            ui_label=UI_LABELS[nid],
            zone_id=NODE_ZONE[nid],
        )

    nodes = [node(RESERVOIR_ID, NodeType.RESERVOIR, ft_to_m(RESERVOIR_HEAD_FT), None)]
    nodes += [node(j, NodeType.JUNCTION, ft_to_m(e), gpm_to_m3s(d)) for j, (e, d) in JUNCTIONS.items()]
    nodes.append(node(TANK_ID, NodeType.TANK, ft_to_m(TANK_ELEVATION_FT), None))
    nodes.sort(key=lambda n: int(n.node_id))

    links = [
        LinkConfig(
            link_id=pid,
            link_type=LinkType.PIPE,
            start_node=s,
            end_node=e,
            length_m=ft_to_m(length_ft),
            diameter_m=in_to_m(diam_in),
            roughness_hw=HW_ROUGHNESS,
            initial_status=LinkStatus.OPEN,
            zone_id=LINK_ZONE[pid],
        )
        for pid, (s, e, length_ft, diam_in) in PIPES.items()
    ]
    links.append(
        LinkConfig(
            link_id=PUMP_ID,
            link_type=LinkType.PUMP,
            start_node=PUMP_START,
            end_node=PUMP_END,
            initial_status=LinkStatus.OPEN,
            zone_id=LINK_ZONE[PUMP_ID],
        )
    )
    return NetworkConfig(
        network_id=network_id,
        source="epanet_tutorial",
        inp_path=f"config/networks/{network_id}.inp",
        nodes=nodes,
        links=links,
        zones=[Zone(zone_id=z, name=n) for z, n in ZONES.items()],
        hydraulics=HydraulicsConfig(
            demand_model="PDD",
            required_pressure_m=REQUIRED_PRESSURE_M,
            minimum_pressure_m=MINIMUM_PRESSURE_M,
            headloss="H-W",
            tank_init_level_m=TANK_INIT_LEVEL_M,
        ),
        taps=[TapDef(tap_id=t, node_id=n) for t, n in TAPS.items()],
        valves=[ValveDef(valve_id=v, link_id=p, impl="pipe_status") for v, p in VALVES.items()],
    )


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR = REPO_ROOT / "config" / "networks"


def export_network_config(out_dir: Path = DEFAULT_CONFIG_DIR) -> NetworkConfig:
    """Write `<network_id>.json` and `<network_id>.inp` (canonical UNSPLIT network) to `out_dir`."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = network_config()
    (out_dir / f"{cfg.network_id}.json").write_text(cfg.model_dump_json(indent=2) + "\n")
    wntr.network.write_inpfile(build_network(pipe_split_pos=None), str(out_dir / f"{cfg.network_id}.inp"))
    return cfg


def load_network_config(path: Path | None = None) -> NetworkConfig:
    """Load and validate the exported NetworkConfig (§7.1)."""
    p = Path(path) if path is not None else DEFAULT_CONFIG_DIR / f"{NETWORK_ID}.json"
    return NetworkConfig.model_validate_json(p.read_text())


if __name__ == "__main__":
    export_network_config()
    print(f"wrote {DEFAULT_CONFIG_DIR}/{NETWORK_ID}.{{json,inp}}")
