"""Step 1 tests: canonical network build (BACKBONE §6)."""

from __future__ import annotations

import pytest
import wntr

import sim.engine.network as N  # noqa: N812

HEALTHY = ["2", "3", "4", "5", "6", "7"]
ABS = 1e-3


def _run(wn):
    return wntr.sim.WNTRSimulator(wn).run_sim()


def test_counts_unsplit():
    wn = N.build_network(pipe_split_pos=None)
    assert (wn.num_reservoirs, wn.num_junctions, wn.num_tanks, wn.num_pumps) == (1, 6, 1, 1)
    assert wn.num_pipes == 8


def test_counts_split():
    wn = N.build_network()
    assert wn.num_pipes == 16
    assert sum(1 for p in wn.pipe_name_list if p.endswith("_B")) == 8
    assert sum(1 for j in wn.junction_name_list if j.startswith("LK_")) == 8
    assert wn.num_junctions == 14
    for p in N.LEAK_PIPES:
        assert wn.get_node(f"LK_{p}").base_demand == 0.0


def test_si_values():
    wn = N.build_network(pipe_split_pos=None)
    assert wn.get_node("1").base_head == pytest.approx(213.36, abs=ABS)
    elev = {"2": 213.36, "3": 216.408, "4": 213.36, "5": 198.12, "6": 213.36, "7": 213.36}
    for j, e in elev.items():
        assert wn.get_node(j).elevation == pytest.approx(e, abs=ABS)
    dem = {"2": 0, "3": 0.00946, "4": 0.00946, "5": 0.01262, "6": 0.00946, "7": 0}
    for j, d in dem.items():
        assert wn.get_node(j).base_demand == pytest.approx(d, abs=ABS)
    tank = wn.get_node("8")
    assert tank.elevation == pytest.approx(252.984, abs=ABS)
    assert tank.max_level == pytest.approx(6.096, abs=ABS)
    assert tank.diameter == pytest.approx(18.288, abs=ABS)
    assert tank.init_level == pytest.approx(1.07)
    lengths = {"1": 914.4, "2": 1524.0, "6": 2133.6, "8": 2133.6}
    diams = {"1": 0.3556, "2": 0.3048, "3": 0.2032, "6": 0.254, "7": 0.1524}
    for p, v in lengths.items():
        assert wn.get_link(p).length == pytest.approx(v, abs=ABS)
    for p, v in diams.items():
        assert wn.get_link(p).diameter == pytest.approx(v, abs=ABS)
    pump = wn.get_link("9")
    assert pump.get_pump_curve().points[0] == pytest.approx((0.03785, 45.72), abs=ABS)


def test_topology_unsplit():
    wn = N.build_network(pipe_split_pos=None)
    for p, (s, e, _, _) in N.PIPES.items():
        link = wn.get_link(p)
        assert (link.start_node_name, link.end_node_name) == (s, e)
        assert N.canonical_pipe_endpoints(p) == (s, e)
    pump = wn.get_link("9")
    assert (pump.start_node_name, pump.end_node_name) == ("1", "2")


def test_topology_split():
    wn = N.build_network(pipe_split_pos={p: 0.3 for p in N.LEAK_PIPES})
    for p, (s, e, length_ft, _) in N.PIPES.items():
        a, b = wn.get_link(p), wn.get_link(f"{p}_B")
        assert (a.start_node_name, a.end_node_name) == (s, f"LK_{p}")
        assert (b.start_node_name, b.end_node_name) == (f"LK_{p}", e)
        assert a.length == pytest.approx(0.3 * N.ft_to_m(length_ft))
        assert wn.get_node(f"LK_{p}").coordinates is not None


def test_tap_demand_entry():
    wn = N.build_network(pipe_split_pos=None)
    for j in N.TAPS.values():
        node = wn.get_node(j)
        taps = [d for d in node.demand_timeseries_list if d.category == N.TAP_DEMAND_CATEGORY]
        assert len(taps) == 1 and taps[0].base_value == 0.0 and taps[0].pattern_name == "1"
        assert node.base_demand == pytest.approx(N.gpm_to_m3s(150.0))
    assert len(wn.get_node("5").demand_timeseries_list) == 1


def test_options_and_operations():
    wn = N.build_network(reservoir_head_offset_m=2.0, pump_speed=0.9, duration_s=600)
    o = wn.options
    assert o.hydraulic.demand_model == "PDA"  # WNTR alias of PDD
    assert (o.hydraulic.required_pressure, o.hydraulic.minimum_pressure) == (20.0, 0.0)
    assert o.time.hydraulic_timestep == o.time.report_timestep == 300
    assert o.time.pattern_timestep == 3600 and o.time.duration == 600
    assert wn.get_node("1").base_head == pytest.approx(215.36, abs=ABS)
    assert wn.get_link("9").speed_timeseries.base_value == 0.9


def test_diurnal_multipliers():
    m = N.diurnal_multipliers()
    assert len(m) == 24 and all(v > 0 for v in m)
    assert 0.7 <= sum(m) / 24 <= 1.3
    assert N.diurnal_multipliers(N.DEFAULT_DEMAND_PROFILE) == m
    hi = N.DEFAULT_DEMAND_PROFILE.model_copy(update={"global_mult": 1.2})
    assert N.diurnal_multipliers(hi) == pytest.approx([1.2 * v for v in m])


def test_unknown_network_id():
    with pytest.raises(ValueError):
        N.build_network("nope")


def test_eps_pressures_and_presplit_equivalence():
    plain = _run(N.build_network(pipe_split_pos=None))
    split = _run(N.build_network())
    p, ps = plain.node["pressure"], split.node["pressure"]
    assert len(p) == 289
    assert p[HEALTHY[0:1] + HEALTHY[1:]].min().min() >= 20.0
    assert (ps[HEALTHY] - p[HEALTHY]).abs().max().max() <= 1e-4
