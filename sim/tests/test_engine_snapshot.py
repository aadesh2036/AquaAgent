"""Step 3 tests: WNTR results -> canonical HydraulicSnapshot, mass balance."""

from __future__ import annotations

import pytest
import wntr

from shared.contracts.models import HydraulicSnapshot
from sim.engine import network as net
from sim.engine.mass_balance import check_mass_balance, mass_balance_error_m3s, results_mass_balance_error
from sim.engine.snapshot import to_snapshots


@pytest.fixture(scope="module")
def run():
    wn = net.build_network()
    res = wntr.sim.WNTRSimulator(wn).run_sim()
    return wn, res, to_snapshots(res, wn=wn)


def test_snapshots_valid_and_canonical(run):
    _, _, snaps = run
    assert len(snaps) == 289
    for s in snaps:
        HydraulicSnapshot.model_validate(s.model_dump())
        assert list(s.nodes) == net.CANONICAL_NODES
        assert list(s.links) == net.CANONICAL_LINKS
        assert list(s.tanks) == ["8"] and list(s.pumps) == ["9"]
        assert s.hidden is not None and s.hidden.leak_nodes == {}


def test_mass_balance_every_step(run):
    _, res, snaps = run
    assert results_mass_balance_error(res) <= 1e-4
    assert all(check_mass_balance(s) for s in snaps)
    assert max(abs(mass_balance_error_m3s(s)) for s in snaps) < 1e-8


def test_physical_sanity(run):
    _, _, snaps = run
    for s in snaps:
        assert min(s.nodes[j].pressure_m for j in "234567") >= 20.0
        assert 0.0 <= s.tanks["8"].level_m <= 6.096 + 1e-6
        assert s.pumps["9"].head_gain_m > 0
        assert s.links["1"].flow_m3s == pytest.approx(s.pumps["9"].flow_m3s, abs=1e-6)
        assert s.nodes["1"].demand_m3s < 0


def test_tank_sign_and_volume(run):
    _, _, snaps = run
    a, b = snaps[0], snaps[1]
    # tank net inflow equals pipe 6 flow (7 -> 8 positive = filling); level moves accordingly
    assert a.tanks["8"].net_inflow_m3s == pytest.approx(a.links["6"].flow_m3s, abs=1e-6)
    assert (b.tanks["8"].level_m - a.tanks["8"].level_m) * a.tanks["8"].net_inflow_m3s >= 0
    assert a.tanks["8"].volume_m3 == pytest.approx(3.14159265 * 18.288**2 / 4 * 1.07, rel=1e-4)


def test_base_demand_uses_pattern(run):
    _, _, snaps = run
    assert snaps[0].nodes["3"].base_demand_m3s != snaps[84].nodes["3"].base_demand_m3s
    assert snaps[0].nodes["2"].base_demand_m3s == 0.0
