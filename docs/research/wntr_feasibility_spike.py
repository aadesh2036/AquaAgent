"""WNTR feasibility spike for net_epa_tutorial_v1 (research evidence for backbone/1.1.0).

NOT production code. Module 01 owns the real implementation (`sim/engine/`), built from the tables in
BACKBONE §6 using shared/units. This script hard-codes ft/in/gpm constants only to reproduce the
measurements in docs/research/WNTR_FEASIBILITY.md.

Run (needs Python 3.12 + wntr==1.5.0):
    .venv/bin/python docs/research/wntr_feasibility_spike.py
"""

from __future__ import annotations

import time

import wntr

FT, IN, GPM = 0.3048, 0.0254, 6.30901964e-5
JUNCTIONS = ["2", "3", "4", "5", "6", "7"]
SENSOR_NODES = ["2", "4", "6"]

# EPANET 2.2 Quick Start, Table 2.1/2.2 + Fig. 2.1 (BACKBONE §6.1–6.2)
NODES = {  # id: (elevation ft, base demand gpm, xy)
    "2": (700, 0, (90, 35)),
    "3": (710, 150, (143, 35)),
    "4": (700, 150, (143, 100)),
    "5": (650, 200, (143, 165)),
    "6": (700, 150, (205, 100)),
    "7": (700, 0, (205, 35)),
}
PIPES = {  # id: (start, end, length ft, diameter in)
    "1": ("2", "3", 3000, 14),
    "2": ("3", "7", 5000, 12),
    "3": ("3", "4", 5000, 8),
    "4": ("4", "6", 5000, 8),
    "5": ("7", "6", 5000, 8),
    "6": ("7", "8", 7000, 10),
    "7": ("4", "5", 5000, 6),
    "8": ("5", "6", 7000, 6),
}


def build(presplit: bool = False) -> wntr.network.WaterNetworkModel:
    wn = wntr.network.WaterNetworkModel()
    wn.add_pattern("1", [0.5, 1.3, 1.0, 1.2])  # tutorial's 6-h pattern (spike only)
    wn.options.time.pattern_timestep = 6 * 3600
    wn.add_reservoir("1", base_head=700 * FT, coordinates=(15, 35))
    for node_id, (elev_ft, demand_gpm, xy) in NODES.items():
        wn.add_junction(
            node_id, base_demand=demand_gpm * GPM, elevation=elev_ft * FT, demand_pattern="1", coordinates=xy
        )
    wn.add_tank(
        "8",
        elevation=830 * FT,
        init_level=3.5 * FT,
        min_level=0,
        max_level=20 * FT,
        diameter=60 * FT,
        coordinates=(265, 35),
    )
    for pipe_id, (start, end, length_ft, diam_in) in PIPES.items():
        wn.add_pipe(pipe_id, start, end, length=length_ft * FT, diameter=diam_in * IN, roughness=100)
    wn.add_curve("1", "HEAD", [(600 * GPM, 150 * FT)])
    wn.add_pump("9", "1", "2", pump_type="HEAD", pump_parameter="1")

    opts = wn.options
    opts.hydraulic.demand_model = "PDD"
    opts.hydraulic.required_pressure = 20
    opts.hydraulic.minimum_pressure = 0
    opts.time.hydraulic_timestep = 300
    opts.time.report_timestep = 300
    opts.time.duration = 24 * 3600
    if presplit:  # BACKBONE §6.3: pre-split every pipe so leaks never change topology mid-run
        for pipe_id in PIPES:
            wn = wntr.morph.split_pipe(wn, pipe_id, f"{pipe_id}_B", f"LK_{pipe_id}", split_at_point=0.5)
    return wn


def run(wn: wntr.network.WaterNetworkModel):
    return wntr.sim.WNTRSimulator(wn).run_sim()


def mass_balance_error(results) -> float:
    total = results.node["demand"].sum(axis=1) + results.node["leak_demand"].sum(axis=1)
    return float(total.abs().max())


def main() -> None:
    t0 = time.time()
    base = run(build())
    pressure = base.node["pressure"]
    print(f"24h EPS: {len(pressure)} steps in {time.time() - t0:.2f}s")
    print(
        f"healthy junction pressure min/max: {pressure[JUNCTIONS].min().min():.2f} / {pressure[JUNCTIONS].max().max():.2f} m"
    )
    print(f"tank level range: {pressure['8'].min():.2f}–{pressure['8'].max():.2f} m")
    print(f"mass balance (healthy): {mass_balance_error(base):.2e} m3/s")

    split = run(build(presplit=True))
    d_split = (split.node["pressure"][JUNCTIONS] - pressure[JUNCTIONS]).abs().max().max()
    print(f"pre-split vs plain max|dP|: {d_split:.2e} m")

    leaky_wn = build(presplit=True)
    leaky_wn.get_node("LK_4").add_leak(leaky_wn, area=1.5e-4, start_time=12 * 3600)
    leaky = run(leaky_wn)
    d_sensors = (
        leaky.node["pressure"].loc[14 * 3600, SENSOR_NODES]
        - split.node["pressure"].loc[14 * 3600, SENSOR_NODES]
    )
    print(
        f"pipe-4 leak (1.5e-4 m2) dP at S1/S2/S3 @14h: {d_sensors.round(3).tolist()} m; "
        f"leak {leaky.node['leak_demand'].loc[14 * 3600, 'LK_4'] * 1000:.2f} L/s; mass balance {mass_balance_error(leaky):.2e}"
    )

    step_wn = build(presplit=True)
    step_wn.options.time.duration = 10 * 3600
    run(step_wn)
    step_wn.get_node("LK_4").add_leak(step_wn, area=1.5e-4, start_time=12 * 3600)
    step_wn.options.time.duration = 24 * 3600
    resumed = run(step_wn)
    d_restart = (
        (
            resumed.node["pressure"].loc[14 * 3600, SENSOR_NODES]
            - leaky.node["pressure"].loc[14 * 3600, SENSOR_NODES]
        )
        .abs()
        .max()
    )
    print(
        f"stop/restart vs full run max|dP| @14h: {d_restart:.2e} m (resumed index starts at {resumed.node['pressure'].index[0]} s)"
    )

    tick_wn = build(presplit=True)
    tick_wn.options.time.duration = 0
    run(tick_wn)
    t0 = time.time()
    for k in range(1, 25):
        tick_wn.options.time.duration = k * 300
        run(tick_wn)
    print(f"single 300-s step advance: {(time.time() - t0) / 24 * 1000:.0f} ms/step")

    system_demand = split.node["demand"][JUNCTIONS].sum(axis=1).mean()
    for area in [2e-5, 8e-5, 2.5e-4, 6e-4, 3e-3]:
        wn = build(presplit=True)
        wn.get_node("LK_4").add_leak(wn, area=area, start_time=0)
        res = run(wn)
        leak = res.node["leak_demand"]["LK_4"].mean()
        print(
            f"area {area:.1e} m2 -> leak {leak * 1000:.2f} L/s = {leak / system_demand * 100:.1f}% of mean demand; "
            f"min junction P {res.node['pressure'][JUNCTIONS].min().min():.1f} m"
        )


if __name__ == "__main__":
    main()
