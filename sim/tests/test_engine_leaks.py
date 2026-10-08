"""Step 4 tests: leaks."""

from __future__ import annotations

import pytest
import wntr

from sim.engine import network as net
from sim.engine.leaks import (
    MAX_LEAK_AREA_M2,
    add_junction_leak,
    add_pipe_leak,
    clear_leak_now,
    set_leak_now,
)
from sim.engine.mass_balance import check_mass_balance, results_mass_balance_error
from sim.engine.snapshot import to_snapshot

H = 3600
AREA = 1.5e-4
JUNC = ["2", "3", "4", "5", "6", "7"]


def _run(wn):
    return wntr.sim.WNTRSimulator(wn).run_sim()


@pytest.fixture(scope="module")
def base():
    return _run(net.build_network())


def test_pipe4_leak_lowers_sensors(base):
    wn = net.build_network()
    assert add_pipe_leak(wn, "4", AREA, 12 * H) == "LK_4"
    res = _run(wn)
    for n in ("4", "6"):
        d = base.node["pressure"].loc[14 * H, n] - res.node["pressure"].loc[14 * H, n]
        assert d > 0.5
    assert results_mass_balance_error(res) <= 1e-4
    snap = to_snapshot(res, 14 * H, wn=wn)
    assert snap.hidden.leak_nodes["LK_4"].leak_m3s > 0
    assert list(snap.nodes) == net.CANONICAL_NODES and list(snap.links) == net.CANONICAL_LINKS
    assert check_mass_balance(snap)
    assert to_snapshot(res, 6 * H, wn=wn).hidden.leak_nodes == {}


def test_junction5_leak(base):
    wn = net.build_network()
    add_junction_leak(wn, "5", 3e-4, 0)
    res = _run(wn)
    assert res.node["pressure"].loc[6 * H, "5"] < base.node["pressure"].loc[6 * H, "5"] - 0.1
    snap = to_snapshot(res, 6 * H, wn=wn)
    assert snap.nodes["5"].leak_m3s > 0 and check_mass_balance(snap)


def test_set_leak_now_matches_scheduled():
    ref_wn = net.build_network()
    add_pipe_leak(ref_wn, "4", AREA, 10 * H)
    ref = _run(ref_wn)

    wn = net.build_network(duration_s=10 * H)
    _run(wn)
    set_leak_now(wn, "LK_4", AREA)
    wn.options.time.duration = 24 * H
    res = _run(wn)
    a = res.node["pressure"].loc[11 * H : 24 * H, JUNC]
    b = ref.node["pressure"].loc[11 * H : 24 * H, JUNC]
    # one-step lag: the state at the pause time was already computed without the leak (max ~3e-3 m)
    assert (a - b).abs().max().max() < 5e-3
    assert res.node["leak_demand"].loc[12 * H, "LK_4"] > 0

    clear_leak_now(wn, "LK_4")
    wn.options.time.duration = 26 * H
    res2 = _run(wn)
    assert res2.node["leak_demand"].loc[25 * H, "LK_4"] == 0.0


def test_invalid_inputs():
    wn = net.build_network()
    with pytest.raises(ValueError):
        add_junction_leak(wn, "8", AREA, 0)
    with pytest.raises(ValueError):
        add_junction_leak(wn, "1", AREA, 0)
    with pytest.raises(ValueError):
        add_junction_leak(wn, "4", 0.0, 0)
    with pytest.raises(ValueError):
        add_pipe_leak(wn, "4", MAX_LEAK_AREA_M2 * 2, 0)
    with pytest.raises(ValueError):
        add_pipe_leak(wn, "9", AREA, 0)
    with pytest.raises(ValueError):
        add_pipe_leak(net.build_network(pipe_split_pos=None), "4", AREA, 0)
    with pytest.raises(ValueError):
        set_leak_now(wn, "8", AREA)
