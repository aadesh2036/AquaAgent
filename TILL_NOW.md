# TILL_NOW.md — build status log

> What has been done, what is next, and where everything lives.
> **Update rule (INSTRUCTIONS.md §8):** every agent appends to the Progress log and updates Module status at the end of every step, with evidence. Facts only.
> Contract: `backbone/1.1.0` ([BACKBONE.md](BACKBONE.md)). Process: [INSTRUCTIONS.md](INSTRUCTIONS.md). Runbook: [docs/RUNBOOK.md](docs/RUNBOOK.md).

---

## 1. Current state at a glance (2026-10-08)

**Phase:** setup complete; **module 01 (simulation engine) done — gate G1 passed** on branch `simulation` (commits `536af6a`…`ba1926e`). The `aquaagent-sim` container builds and serves the §7.14.2 API locally. All other modules are still stubs.

**Build focus (BACKBONE §2, v1.1.0):** T1 = the **local MVP detection loop**: simulation → dataset → MLP → residual detector → challenge → template explanation → SVG UI. Gate **MVP** must pass before any AWS / SageMaker / localisation / Bedrock work.

**Next action:** link the simulation to the frontend: module 08 steps 1–2 (orchestrator skeleton: session, network state, step, tap/pipe/valve via the visibility filter, calling the sim API) + module 09 steps 1–3 (live SVG network). Then module 02 (data generation). AWS deployment stays last (owner decision).

**Git:** branch `simulation`. Commits are made per step after the lead's review (owner request, 2026-10-08). No pushes.

## 2. Module status

| # | Module | Gate | Tier | Status | Next step |
|---|---|---|---|---|---|
| — | shared/contracts + units + ids | all | T1 | **done** (`backbone/1.1.0`) | — |
| 01 | [Simulation engine](docs/modules/01_SIMULATION_ENGINE.md) | G1 | **T1 core** | **done (G1 passed)** — 8 steps, last = step 8 (container + smoke + docs) | — |
| 02 | [Data generation](docs/modules/02_DATA_GENERATION.md) | G2 | T1 | stubs | after 08/09 link-up |
| 04 | [ML predictor](docs/modules/04_ML_PREDICTOR.md) | G4 | T1 | stubs | after 02 |
| 05 | [Detector (+ localisation T2c)](docs/modules/05_ANOMALY_LOCALISATION.md) | G5 | T1 / T2c | stubs | after 04 |
| 07 | [Explanation: template (+ Bedrock T2d)](docs/modules/07_AQUAAGENT_BEDROCK.md) | G7 | T1 / T2d | stubs | step 1 anytime |
| 08 | [Orchestrator API](docs/modules/08_ORCHESTRATOR_API.md) | G8 + **MVP** | T1 | stubs | **steps 1–2 next** (sim API ready) |
| 09 | [Frontend](docs/modules/09_FRONTEND.md) | G9 | T1 | skeleton | step 1 anytime (mock) |
| 10 | [Demo and pitch](docs/modules/10_DEMO_AND_PITCH.md) | G10 | T1 | — | after MVP |
| 03 | [AWS infra](docs/modules/03_AWS_INFRA.md) | G3 | T2a | scripts written, not executed | after MVP |
| 06 | [SageMaker](docs/modules/06_SAGEMAKER.md) | G6 | T2b | stubs | after T2a |

## 3. What the setup produced (where to look)

| Area | Files |
|---|---|
| Contract | `BACKBONE.md` v1.1.0 (changelog §17); `docs/BACKBONE_ISSUES.md` = resolution log BI-01…BI-24 (all resolved) |
| Research | `docs/research/WNTR_FEASIBILITY.md` (sources + measurements), `wntr_feasibility_spike.py` (`make feasibility`), `epanet22_fig2_1_tutorial_network.jpeg` |
| Process | `INSTRUCTIONS.md` (read before any module), this file |
| Plans | `docs/modules/01…10` (13 sections each, with a self-contained agent prompt), `docs/RUNBOOK.md` (Part A MVP local, Part B AWS, Part C demo/teardown) |
| AWS primers (T2) | `docs/aws/00…04` |
| Code | `shared/` (Pydantic + TS contracts, ids, units, tests), stubs in `sim/ ml/ api/ frontend/`, `infra/` scripts 00–15/90/99, `scripts/datagen_local.sh`, `Makefile`, `docker-compose.yml`, CI |
| Reference docs | `CONTEXT/` (handoff moved here from the repo root, spec, prototype guide, briefing, README_FOR_SIM) |

## 4. Key decisions in backbone/1.1.0 (why things look the way they do)
1. **Scope:** MVP detection loop first; T2 in order a→d (AWS deploy → SageMaker → localisation → Bedrock); ds2 scenario types, sensor faults, GNN and what-if are T3.
2. **Network:** there is no official tutorial `.inp`, so connectivity, zones and UI coordinates are stated in BACKBONE §6.2 (from EPANET 2.2 Fig. 2.1).
3. **Single 300-s cadence** for dataset and interactive mode (measured 18 ms/step). Speed 1×/5×/20× = 1/5/20 steps per second.
4. **Pre-split pipes**, so leaks never change topology mid-run (ΔP ≤ 1.7e-5 m). Stop/restart stepping == full run.
5. **ds1 = 1,200 sims, 8 types**, generated locally in minutes. ECS datagen is T3.
6. **Leave-one-out over all 5 sensors** (`leave_one_out_flow` added). Predictor in-process in T1.
7. **TemplateReporter** is the T1 explanation. Bedrock (inference profile, 20-s budget) is T2d.
8. **Python 3.12 + `wntr==1.5.0`** (`make setup` uses uv; WNTR has no 3.14 wheels).

## 5. Evidence (setup)
| Check | Result |
|---|---|
| `make setup` | Python 3.12.14, wntr 1.5.0 |
| `make feasibility` | 24 h EPS 0.27 s; healthy P 34.9–58.0 m; mass balance 1e-17; pre-split ΔP 1.7e-5 m; restart == full run; 18 ms/step; pipe-4 leak 3 L/s → −0.8 m at S2/S3 |
| `make lint` | ruff clean; `bash -n` on all infra scripts |
| `make contracts-test` | pytest 36 passed (BACKBONE 1.1.0 examples round-trip), node 7 passed |
| Hard-coded IDs/secrets grep | no hits |
| AWS scripts | **not executed** (T2) |

## 6. Open items (owner)
- [ ] Day-1 optional 5-minute AWS items: budget alert (`01_budget_alert.sh`) and the Bedrock region check (`14_bedrock_check.sh`).
- [ ] RUNBOOK "Values to confirm" V1–V9 (all T2).
- [x] AWS timing: **owner decision (2026-10-08): build all modules locally first; deployment (T2a/T2b/T2d) is done last to save AWS credits.** Do not run any `infra/scripts/*` until the owner says so.

## 7. Progress log
| When | Module | Step | Status | Files | Evidence | Notes |
|---|---|---|---|---|---|---|
| 2026-10-08 | setup | repo skeleton + docs + contracts (backbone/1.0.0) | done | see §3 | lint + contracts green | — |
| 2026-10-08 | setup | resolve BACKBONE issues → backbone/1.1.0; WNTR feasibility; MVP re-tier; Python 3.12 env | done | BACKBONE.md, docs/*, shared/contracts, Makefile, config/generation/ds1.yaml | `make feasibility`, `make lint`, `make contracts-test` green | handoff moved to `CONTEXT/` |
| 2026-10-08 | 01 | 1 network build | done | sim/engine/network.py, sim/tests/test_engine_network.py | 10 tests; 289-step EPS, junction P 31.2–59.8 m; pre-split vs unsplit ΔP ≤ 1e-4 m | `split_pipe` keeps canonical id `p` as the UPSTREAM half; tap demand = 2nd demand entry category `tap`; WNTR stores PDD as "PDA" |
| 2026-10-08 | 01 | 2 NetworkConfig export | done | sim/engine/network.py, config/networks/net_epa_tutorial_v1.{json,inp}, sim/tests/test_engine_export.py | JSON == constants; 8 nodes / 9 links; .inp round-trip max ΔP 1.06e-5 m | tolerance 1e-4 m because the .inp is written in US units with rounding (20 m → 28.43 psi) |
| 2026-10-08 | 01 | 3 snapshot + mass balance | done | sim/engine/snapshot.py, mass_balance.py, sim/tests/test_engine_snapshot.py | 289 snapshots validate; mass balance < 1e-8 m3/s | tank `demand` > 0 = filling (== pipe 6 flow); reservoir demand < 0 |
| 2026-10-08 | 01 | 4 leaks | done | sim/engine/leaks.py, sim/tests/test_engine_leaks.py | pipe-4 leak 1.5e-4 m2 lowers S2/S3 > 0.5 m; set_leak_now vs scheduled max ΔP 3.1e-3 m | one-step event lag; `_leak_status` has no public setter in WNTR 1.5 (private attr used) |
| 2026-10-08 | 01 | 5–6 session + fork | done | sim/engine/session.py, sim/tests/test_engine_session.py | stepwise == replay ≤ 1e-6 m over 288 steps; CLOSE == WNTR control ≤ 1e-6 m; 20 steps ≈ 32 ms | pipe status via `link.initial_status` (restart re-reads it); events act from the NEXT step; rollback on failure by replay |
| 2026-10-08 | 01 | 7 FastAPI server | done | sim/server/app.py, sim/cli.py, sim/tests/test_server.py, requirements-dev.txt | 42 sim tests passed; live curl health/create/advance OK | LRU sessions + per-session lock; 422/404/503 mapping |
| 2026-10-08 | 01 | 8 container + smoke + docs | done (G1 passed) | sim/smoke.py, sim/Dockerfile, .dockerignore, docker-compose.yml, Makefile, sim/README.md, docs/modules/01 §9 | `make sim-smoke` OK (leak 3.30 L/s, 5 ms/step); image 784 MB; container health `{"status":"ok","wntr_version":"1.5.0"}` | podman ignores HEALTHCHECK in OCI format (works with `--format docker`); server needs ~6–8 s to start |
| 2026-10-08 | 01 | review fix: smoke compares vs no-leak twin | done | sim/smoke.py | pipe-4 leak 1.5e-4 m² at 12 h → after 1 h ΔP vs twin S1 −0.62, S2 −0.92, S3 −0.92 m; leak 3.30 L/s | earlier before/after comparison mixed in the diurnal change (showed only −0.06 m) |
| 2026-10-08 | 01 | commits | done | branch `simulation` | `536af6a` step 1 · `418bdf3` step 2 · `d62cee3` step 3 · `ebaa4fe` step 4 · `0f0dc49` steps 5–6 · `22c7900` step 7 · `ba1926e` step 8 | 42 sim tests, `make lint`, `make sim-smoke` green |
