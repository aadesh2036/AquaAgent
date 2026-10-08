# 01_SIMULATION_ENGINE.md
Backbone version: backbone/1.1.0 | Gate: **G1** | Tier: **T1 (core)** | Est. effort: 8 h
Depends on: — (shared/contracts done, feasibility validated) | Blocks: 02, 05, 08, 09 (real topology), 03 (image) | Schedule slot: Day 1 AM–PM (BACKBONE §13)

> **The simulation is the core of AquaAgent.** Every number downstream (dataset, model, demo) is only as true as this module.
> The approach below has already been validated: see `docs/research/WNTR_FEASIBILITY.md` (run `make feasibility`). `docs/research/wntr_feasibility_spike.py` is a working reference, but it is not production code.

## 1. Purpose
Build the physics ground truth: the EPA 2.2 tutorial network `net_epa_tutorial_v1` in WNTR (PDD, real orifice leaks). It must run as a 24-h extended-period simulation and as a stepwise interactive session at the single 300-s cadence. Every state maps to the canonical `HydraulicSnapshot`. The module ships as the `aquaagent-sim` image (`serve | generate | merge`) serving the internal sim API.

## 2. Inputs — contracts consumed
- §6.1 nodes, **§6.2 links incl. start→end, zones and UI coordinates**, §6.3 hydraulics (PDD 20/0, pre-split pipe leaks, stepping), §6.4 sensor layout (`config/sensors/sensors_default_v1.json`)
- §5.1 IDs (`LK_<pipe>`, `<pipe>_B`), §5.2 units (state layer SI), §5.3 time (300 s everywhere), §5.4 seeds, §5.5 pins (Python 3.12, `wntr==1.5.0`)
- §7.1 `NetworkConfig`, §7.2 `ScenarioSpec` (demand profile + fault fields used by the builder), §7.3 `SimEvent`
- `shared/units.py` (ft/in/gpm → SI), `shared/contracts/ids.py`

## 3. Outputs — contracts produced
- `config/networks/net_epa_tutorial_v1.{inp,json}`: §7.1 `NetworkConfig`, built from §6 (no official `.inp` exists, BI-21)
- §7.4 `HydraulicSnapshot` (canonical, `hidden` populated)
- §7.14.2 internal sim HTTP API (:8000)
- Python API for module 02 (batch) and module 05 (signatures, T2c): see §11
- `aquaagent-sim` Docker image

## 4. Files owned
`sim/engine/` (`network.py`, `leaks.py`, `snapshot.py`, `mass_balance.py`, `session.py`, `demand.py`†), `sim/server/app.py`, `sim/cli.py` (`serve`; dispatch for `generate`/`merge`), `sim/Dockerfile`, `sim/requirements.txt`, `sim/tests/test_engine_*.py`, `sim/tests/test_server.py`, `config/networks/*`, `sim/README.md`.
† The demand-pattern *function* used by both interactive and batch lives in `sim/scenarios/demand.py` (owned by 02). Module 01 calls it with a default profile, and until 02 implements it, 01 may use a fixed default diurnal pattern in `sim/engine/network.py`.

## 5. Design decisions (binding)
- **Build from BACKBONE §6 tables** via `shared/units` (ft, in and gpm are converted once). Export the `.inp` with `wntr.network.write_inpfile` and the JSON as `NetworkConfig`. *Rejected:* hand-maintained `.inp` (two sources of truth); EPANET Net1/Net3 (different network).
- **WNTRSimulator only** (leaks + stop/restart need it). *Rejected:* EpanetSimulator (leaks via emitters only, model reset on every run).
- **PDD** `required_pressure_m=20`, `minimum_pressure_m=0`. The healthy baseline is 34.9–58.0 m, measured. Record the values in `NetworkConfig.hydraulics`.
- **Pre-split pipes (§6.3, BI-23):** when a model is built, every pipe 1–8 is split with `wntr.morph.split_pipe(wn, p, f"{p}_B", f"LK_{p}", split_at_point=pos)`. `pos=0.5` for interactive sessions; batch callers pass `pos` per pipe. A pipe leak is `wn.get_node(f"LK_{p}").add_leak(wn, area=…, discharge_coeff=0.75, start_time=…, end_time=…)`. A junction leak is the same call on the junction. **Topology never changes after build.** *Rejected:* splitting mid-run (topology change during a paused simulation is the §14 risk).
- **Stepping:** one `WaterNetworkModel` per session. `advance(n)` sets `wn.options.time.duration += n*300` and runs `WNTRSimulator(wn).run_sim()`, and the results contain only the new steps (measured: identical to a full run, ≈18 ms/step). **Fallback:** replay from t=0 with the event log + seed, using a fresh build with all events applied with their `sim_time_s`. Keep the fallback behind a flag and cover it with the same test.
- **Interactive controls:** tap = demand multiplier on the tap's junction from now on (implement as a time-varying demand override, so earlier history is unchanged). **CLOSE/valve** = `pipe.initial_status` CLOSED via a WNTR control at the current time. **RESET (pipe)** = leak `end_time = now`. Every control must be expressible as a `SimEvent` so replay works.
- **Canonical snapshot (§7.4):** canonical link `p` reports the **upstream half's** flow (the half that starts at the original start node). `LK_*` states go only to `hidden.leak_nodes`. `nodes`/`links` keys must equal the canonical set exactly (8 nodes, 9 links).
- **Mass balance:** `|Σ demand + Σ leak_demand| ≤ 1e-4 m³/s` per step (WNTR reports reservoir/tank as negative demand).
- **Sim server returns full truth.** Hiding is the orchestrator's job. Do not import boto3 in `sim/server` (BI-11).
- Randomness only via `numpy.random.Generator(PCG64(seed))` (e.g. the default demand profile noise).

## 6. Implementation plan
| # | Step (≤ 2 h) | Done when |
|---|---|---|
| 1 | `make setup` (Python 3.12, `wntr==1.5.0`); `make feasibility` reproduces the numbers in WNTR_FEASIBILITY.md. `network.build_network(network_id, *, pipe_split_pos=None, demand_profile=None)`: nodes, links, pump (single-point curve), tank, PDD, 300-s options, pre-split pipes. | `pytest sim/tests/test_engine_network.py`: 1 reservoir, 6 junctions, 1 tank, 8 canonical pipes (+8 `_B` halves + 8 `LK_*` when split), 1 pump; elevations/demands/lengths/diameters equal §6 via `shared.units` (abs tol 1e-3); topology == §6.2 table. |
| 2 | `export_network_config()` → `config/networks/net_epa_tutorial_v1.{inp,json}` (zones, taps T1–T3, valve V1, coordinates from §6.2, final hydraulics values). `load_network_config()`. | JSON validates as `NetworkConfig`; the exported `.inp` re-loads with `wntr.network.WaterNetworkModel(inp)` and gives the same 24-h pressures as `build_network()` (±1e-6 m). |
| 3 | `snapshot.to_snapshot(results, t_s, config)` + `mass_balance.py`. 24-h EPS test. | 289 snapshots validate as `HydraulicSnapshot`; mass balance ≤ 1e-4 every step; healthy min junction pressure ≥ 20 m; no `_B`/`LK_` key outside `hidden`. |
| 4 | `leaks.add_junction_leak`, `leaks.add_pipe_leak` (on pre-split `LK_<p>`). | Test vs no-leak twin: a pipe-4 leak of 1.5e-4 m² lowers S2/S3 pressure by > 0.5 m after 2 h; junction-5 leak lowers node-5 pressure; mass balance holds with the leak; `hidden.leak_nodes["LK_4"].leak_m3s > 0`. |
| 5 | `SimSession(network_id, seed, timestep_s=300)`: `apply_event` (TAP_SET, PIPE_FAULT, PIPE_RESET, VALVE_SET, RESET), `advance(steps)`, `snapshot()`, `reset()`; event log. | Test: advance 120 → leak event → advance 168 equals a full replay of the same event log (±1e-6 m); 20 steps in < 1 s. |
| 6 | `fork_what_if(events, horizon)` on a deep copy (pickle; T3 user, but cheap and needed for isolation tests). | Fork leaves the live snapshot byte-identical. |
| 7 | FastAPI `sim/server/app.py`: every §7.14.2 route using `shared.contracts` models; `sim/cli.py serve`. | `pytest sim/tests/test_server.py` (FastAPI TestClient): each route returns a schema-valid body; `/sim/health` reports `wntr_version`. |
| 8 | Dockerfile (`python:3.12-slim`), `make sim-smoke` → a real smoke script (build → 24-h EPS → leak → mass balance → print summary). | `docker build -f sim/Dockerfile -t aquaagent-sim . && docker run -p 8000:8000 aquaagent-sim` serves `/sim/health`; `make sim-smoke` exits 0. |

## 7. AWS steps
None in T1. In T2a the image is pushed by `infra/scripts/05_build_push_images.sh` (module 03).

## 8. Tests
- **Unit:** §6 values via `shared.units`; topology == §6.2; pre-split ΔP ≤ 1e-4 m vs plain; EPS length 289; mass balance; leak effects; stepwise == replay; fork isolation; tap/valve/reset events change the expected elements.
- **Contract conformance:** snapshots → `HydraulicSnapshot`; config → `NetworkConfig`; server routes → §7.14.2 models.
- **Firewall/leakage:** `LK_*` and `_B` only under `hidden`; `sim/server` does not import boto3; same `(config, events, seed)` → identical snapshots.

## 9. Acceptance gate — G1
Copied from BACKBONE §12 (v1.1.0), plus module checks:
- [ ] EPA network built from §6 tables; exported `.inp`/`.json` topology == §6.2 (test)
- [ ] 24 h EPS at 300 s; PDD on; healthy baseline ≥ 20 m
- [ ] junction leak and pre-split pipe leak both change pressures/flows
- [ ] mass balance ≤ 1e-4 m³/s every step
- [ ] stepwise advance == full run (or documented replay fallback)
- [ ] WNTR version pinned (`wntr==1.5.0` confirmed)
- [ ] container runs `serve`
- [ ] (module) all §7.14.2 routes schema-valid; fork isolation green; 20 steps < 1 s

## 10. Risks and fallbacks
- Stepwise misbehaves with controls/overrides (Low; feasibility passed for leaks): replay fallback behind a flag.
- Burst convergence failure (large areas): clamp the area, return `converged=false`, never crash the server.
- Tap override approach fights WNTR patterns: fallback = per-junction pattern rebuilt from the event log on replay.
- **Cut line, end of Day 1 (§13):** if pre-split pipe leaks misbehave → junction leaks only for ds1 and the challenge. Record it in TILL_NOW and tell 02/08.

## 11. Handoff
- To **02**: `build_network(pipe_split_pos=…, demand_profile=…)`, `add_junction_leak`, `add_pipe_leak`, `to_snapshot`, `check_mass_balance`, pinned WNTR version (manifest).
- To **08**: sim API at `AQUA_SIM_URL` (§7.14.2), event semantics, 300-s steps, the advance-speed measurement.
- To **09**: `config/networks/net_epa_tutorial_v1.json` (coordinates, zones, taps, valve).
- To **05 (T2c)**: the same builder for signature simulations.
- To **03 (T2a)**: `sim/Dockerfile` (context = repo root).

## 12. Agent prompt
```
You are implementing module 01 (Simulation Engine) of AquaAgent — the core of the project.
Read, in order and completely: INSTRUCTIONS.md, BACKBONE.md, docs/modules/01_SIMULATION_ENGINE.md,
TILL_NOW.md, docs/research/WNTR_FEASIBILITY.md. Use docs/research/wntr_feasibility_spike.py only as a
working reference. Read nothing else for context.
Implement §6 in order, one step at a time. After each step run its "done when" check, then
`make lint && make contracts-test && .venv/bin/python -m pytest sim/tests`, update TILL_NOW.md, STOP and
report (files changed, exact check output). Only edit files listed in §4. Python 3.12, wntr==1.5.0,
WNTRSimulator only. Build the network from BACKBONE §6 tables via shared/units; pre-split pipes; never
change topology mid-run. Never change contracts. If a contract is wrong, write it under §13 and stop.
Do not create git branches or push.
```

## 13. Proposed Backbone Changes
_(empty)_
