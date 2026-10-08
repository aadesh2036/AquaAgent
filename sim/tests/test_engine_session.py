"""Steps 5-6 tests: SimSession (stepwise, replay, events, fork)."""

from __future__ import annotations

import time

import pytest
import wntr
from wntr.network import LinkStatus as WLinkStatus
from wntr.network.controls import Control, ControlAction

from shared.contracts.models import EventKind, EventSource, HydraulicSnapshot, LinkStatus, SimEvent
from sim.engine import network as net
from sim.engine.session import SimSession, SimulationError

H = 3600


def ev(t, ekind, target=None, **params):
    return SimEvent(
        event_id=f"e{t}{ekind}{target}",
        sim_time_s=t,
        source=EventSource.USER,
        kind=ekind,
        target_id=target,
        params=params,
    )


def adv(s, n):
    out = []
    while n > 0:
        k = min(20, n)
        out += s.advance(k)
        n -= k
    return out


def max_dp(a, b):
    return max(
        abs(x.nodes[n].pressure_m - y.nodes[n].pressure_m) for x, y in zip(a, b, strict=True) for n in x.nodes
    )


def test_creation_and_reset():
    s = SimSession()
    snap = s.snapshot()
    assert snap.sim_time_s == 0 and s.sim_time_s == 0 and list(snap.nodes) == net.CANONICAL_NODES
    adv(s, 5)
    s.apply_event(ev(s.sim_time_s, EventKind.PIPE_FAULT, "4", kind="LEAK"))
    s.reset()
    assert s.sim_time_s == 0 and s.events == [] and s.snapshot().sim_time_s == 0
    assert adv(s, 3)[-1].hidden.leak_nodes == {}
    with pytest.raises(ValueError):
        SimSession(timestep_s=60)


def test_stepwise_equals_replay_mode():
    a, b = SimSession(), SimSession(replay_mode=True)
    out = {}
    for name, s in (("a", a), ("b", b)):
        res = adv(s, 120)
        s.apply_event(ev(s.sim_time_s, EventKind.PIPE_FAULT, "4", kind="LEAK"))
        res += adv(s, 168)
        out[name] = res
    assert len(out["a"]) == 288 and [x.sim_time_s for x in out["a"]] == [300 * (i + 1) for i in range(288)]
    assert max_dp(out["a"], out["b"]) <= 1e-6
    assert out["a"][-1].hidden.leak_nodes["LK_4"].leak_m3s > 0
    assert out["a"][119].hidden.leak_nodes == {}


def test_effective_next_step_only():
    s = SimSession()
    adv(s, 10)
    before = s.snapshot()
    s.apply_event(ev(s.sim_time_s, EventKind.PIPE_FAULT, "4", kind="BURST"))
    assert s.snapshot() == before
    nxt = s.advance(1)[0]
    assert nxt.hidden.leak_nodes["LK_4"].leak_m3s > 0


def test_tap_open_close():
    s = SimSession()
    adv(s, 20)
    base = s.snapshot().nodes["4"].demand_m3s
    s.apply_event(ev(s.sim_time_s, EventKind.TAP_SET, "T2", open=True))
    assert s.snapshot().nodes["4"].demand_m3s == base
    o = s.advance(1)[0]
    pat = o.nodes["4"].base_demand_m3s
    assert o.nodes["4"].demand_m3s == pytest.approx(pat, rel=1e-3)
    assert o.nodes["4"].demand_m3s - base > 0.004
    s.apply_event(ev(s.sim_time_s, EventKind.TAP_SET, "T2", open=False))
    c = s.advance(1)[0]
    assert c.nodes["4"].demand_m3s < o.nodes["4"].demand_m3s - 0.004


def test_valve_and_pipe_close():
    s = SimSession()
    adv(s, 20)
    s.apply_event(ev(s.sim_time_s, EventKind.VALVE_SET, "V1", open=False))
    nxt = s.advance(1)[0]
    assert abs(nxt.links["7"].flow_m3s) < 1e-9 and nxt.links["7"].status == LinkStatus.CLOSED
    s.apply_event(ev(s.sim_time_s, EventKind.VALVE_SET, "V1", open=True))
    assert s.advance(1)[0].links["7"].status == LinkStatus.OPEN


def test_close_matches_wntr_control():
    s = SimSession()
    adv(s, 120)  # 10 h
    s.apply_event(ev(s.sim_time_s, EventKind.PIPE_FAULT, "3", kind="CLOSE"))
    got = adv(s, 100)
    assert abs(got[0].links["3"].flow_m3s) < 1e-9 and got[0].links["3"].status == LinkStatus.CLOSED

    wn = net.build_network()
    wn.add_control(
        "c",
        Control._time_control(
            wn, 10 * H + 300, "SIM_TIME", False, ControlAction(wn.get_link("3"), "status", WLinkStatus.Closed)
        ),
    )
    ref = wntr.sim.WNTRSimulator(wn).run_sim().node["pressure"]
    err = max(abs(g.nodes[n].pressure_m - ref.loc[g.sim_time_s, n]) for g in got for n in "234567")
    assert err < 1e-6


def test_pipe_reset_removes_leak():
    s = SimSession()
    adv(s, 10)
    s.apply_event(ev(s.sim_time_s, EventKind.PIPE_FAULT, "4", kind="LEAK"))
    assert adv(s, 2)[-1].hidden.leak_nodes
    s.apply_event(ev(s.sim_time_s, EventKind.PIPE_FAULT, "5", kind="CLOSE"))
    s.advance(1)
    s.apply_event(ev(s.sim_time_s, EventKind.PIPE_RESET, "4"))
    s.apply_event(ev(s.sim_time_s, EventKind.PIPE_RESET, "5"))
    nxt = s.advance(1)[0]
    assert nxt.hidden.leak_nodes == {} and nxt.links["5"].status == LinkStatus.OPEN
    assert nxt.links["5"].flow_m3s != 0


def test_speed_ms_per_step():
    s = SimSession()
    adv(s, 10)
    t0 = time.perf_counter()
    s.advance(20)
    dt = time.perf_counter() - t0
    print(f"ms/step: {dt / 20 * 1000:.1f}")
    assert dt < 1.0


def test_invalid_events_and_args():
    s = SimSession()
    adv(s, 2)
    bad = [
        ev(0, EventKind.TAP_SET, "T1", open=True),  # time mismatch
        ev(s.sim_time_s, EventKind.TAP_SET, "T9", open=True),
        ev(s.sim_time_s, EventKind.TAP_SET, "T1"),
        ev(s.sim_time_s, EventKind.PIPE_FAULT, "9", kind="LEAK"),
        ev(s.sim_time_s, EventKind.PIPE_FAULT, "4", kind="BOOM"),
        ev(s.sim_time_s, EventKind.PIPE_FAULT, "4", kind="LEAK", area_m2=1.0),
        ev(s.sim_time_s, EventKind.VALVE_SET, "V2", open=True),
        ev(s.sim_time_s, EventKind.PIPE_RESET, "4", foo=1),
    ]
    for b in bad:
        with pytest.raises(ValueError):
            s.apply_event(b)
    assert s.events == []
    for n in (0, 21):
        with pytest.raises(ValueError):
            s.advance(n)
    s.apply_event(ev(s.sim_time_s, EventKind.SPEED, None, factor=2))
    assert len(s.events) == 1


def test_fork_isolated():
    s = SimSession()
    adv(s, 30)
    live_json = s.snapshot().model_dump_json()
    t = s.sim_time_s
    base = SimSession()
    adv(base, 30)
    plain = s.fork_what_if([], 25)
    leaky = s.fork_what_if([ev(t, EventKind.PIPE_FAULT, "4", kind="BURST")], 25)
    assert len(leaky) == 25 and leaky[0].sim_time_s == t + 300
    assert s.snapshot().model_dump_json() == live_json and s.sim_time_s == t and s.events == []
    assert leaky[-1].nodes["6"].pressure_m < plain[-1].nodes["6"].pressure_m - 0.5
    # live continues as if no fork happened
    assert max_dp(s.advance(5), base.advance(5)) <= 1e-9
    assert isinstance(leaky[0], HydraulicSnapshot)


def test_determinism():
    runs = []
    for _ in range(2):
        s = SimSession(seed=7)
        r = adv(s, 20)
        s.apply_event(ev(s.sim_time_s, EventKind.TAP_SET, "T1", open=True))
        s.apply_event(ev(s.sim_time_s, EventKind.PIPE_FAULT, "2", kind="LEAK"))
        r += adv(s, 20)
        runs.append(r)
    # solver round-off is ~1e-14 m between identical runs; assert agreement to 1e-9
    assert max_dp(runs[0], runs[1]) <= 1e-9


def test_failure_rolls_back(monkeypatch):
    s = SimSession()
    adv(s, 10)
    s.apply_event(ev(s.sim_time_s, EventKind.PIPE_FAULT, "4", kind="LEAK"))
    s.advance(2)
    before, t = s.snapshot().model_dump_json(), s.sim_time_s
    real = wntr.sim.WNTRSimulator.run_sim
    calls = {"n": 0}

    def boom(self, *a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("no convergence")
        return real(self, *a, **k)

    monkeypatch.setattr(wntr.sim.WNTRSimulator, "run_sim", boom)
    with pytest.raises(SimulationError):
        s.advance(3)
    assert s.sim_time_s == t and s.snapshot().model_dump_json() == before
    ref = SimSession()
    adv(ref, 10)
    ref.apply_event(ev(ref.sim_time_s, EventKind.PIPE_FAULT, "4", kind="LEAK"))
    ref.advance(2)
    assert max_dp(s.advance(3), ref.advance(3)) <= 1e-9
