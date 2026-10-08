"""G1 smoke: `python -m sim.smoke` (BACKBONE §12). Exit 0 on success, 1 naming the failed check."""

from __future__ import annotations

import sys
import time

import wntr

from shared.contracts.models import EventKind, EventSource, SimEvent
from sim.engine import network as net
from sim.engine.mass_balance import MASS_BALANCE_TOL_M3S, results_mass_balance_error
from sim.engine.session import SimSession

SENSOR_NODES = ("2", "4", "6")  # S1-S3
LEAK_AREA_M2 = 1.5e-4
JUNCTIONS = ["2", "3", "4", "5", "6", "7"]


def run() -> list[str]:
    """Run all checks; return the list of failure messages (empty = success)."""
    failures: list[str] = []
    print(f"wntr {wntr.__version__}")

    res = wntr.sim.WNTRSimulator(net.build_network()).run_sim()
    pressure = res.node["pressure"]
    p_min, p_max = pressure[JUNCTIONS].min().min(), pressure[JUNCTIONS].max().max()
    mb = results_mass_balance_error(res)
    print(
        f"24 h EPS: {len(pressure)} steps, junction P {p_min:.1f}..{p_max:.1f} m, mass balance {mb:.1e} m3/s"
    )
    if len(pressure) != 289:
        failures.append(f"expected 289 steps, got {len(pressure)}")
    if mb > MASS_BALANCE_TOL_M3S:
        failures.append(f"mass balance {mb:.2e} > {MASS_BALANCE_TOL_M3S}")
    if p_min < net.REQUIRED_PRESSURE_M:
        failures.append(f"min junction pressure {p_min:.2f} m < {net.REQUIRED_PRESSURE_M}")

    def run_to_noon(session: SimSession) -> None:
        while session.sim_time_s < 144 * net.TIMESTEP_S:  # 12 h
            session.advance(min(20, 144 - session.sim_time_s // net.TIMESTEP_S))

    s = SimSession(seed=0)
    twin = SimSession(seed=0)  # same session without the leak: compares at the same time of day
    run_to_noon(s)
    run_to_noon(twin)
    s.apply_event(
        SimEvent(
            event_id="smoke_leak",
            sim_time_s=s.sim_time_s,
            source=EventSource.SYSTEM,
            kind=EventKind.PIPE_FAULT,
            target_id="4",
            params={"kind": "LEAK", "area_m2": LEAK_AREA_M2},
            hidden=True,
        )
    )
    t0 = time.perf_counter()
    after = s.advance(12)[-1]
    ms_step = (time.perf_counter() - t0) / 12 * 1000
    baseline = twin.advance(12)[-1]
    leak_lps = sum(v.leak_m3s for v in after.hidden.leak_nodes.values()) * 1000
    deltas = {n: after.nodes[n].pressure_m - baseline.nodes[n].pressure_m for n in SENSOR_NODES}
    delta_txt = " ".join(f"S{i + 1}={deltas[n]:+.2f}" for i, n in enumerate(SENSOR_NODES))
    print(
        f"pipe-4 leak at 12 h ({LEAK_AREA_M2} m2): dP vs no-leak twin after 1 h [{delta_txt}] m; leak {leak_lps:.2f} L/s"
    )
    print(f"session advance: {ms_step:.1f} ms/step")
    if leak_lps <= 0:
        failures.append("leak produced no leak flow")
    if not deltas["4"] < -0.3:
        failures.append(f"leak lowered node-4 pressure by only {-deltas['4']:.3f} m vs twin")
    return failures


def main() -> int:
    failures = run()
    for f in failures:
        print(f"FAILED: {f}", file=sys.stderr)
    print("sim-smoke OK" if not failures else "sim-smoke FAILED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
