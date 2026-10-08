# TILL_NOW.md — build status log

> What has been done, what is next, and where everything lives.
> **Update rule (INSTRUCTIONS.md §8):** every agent appends to the Progress log and updates Module status at the end of every step, with evidence. Facts only.
> Contract: `backbone/1.1.0` ([BACKBONE.md](BACKBONE.md)). Process: [INSTRUCTIONS.md](INSTRUCTIONS.md). Runbook: [docs/RUNBOOK.md](docs/RUNBOOK.md).

---

## 1. Current state at a glance (2026-10-08)

**Phase:** repository setup **complete**. The contracts, docs, stubs and environment are ready, and the simulation approach is feasibility-validated. **No module logic is implemented yet.** Every code file outside `shared/` is a typed stub that raises `NotImplementedError` / exits 2 with `NOT IMPLEMENTED — see docs/modules/NN`.

**Build focus (BACKBONE §2, v1.1.0):** T1 = the **local MVP detection loop**: simulation → dataset → MLP → residual detector → challenge → template explanation → SVG UI. Gate **MVP** must pass before any AWS / SageMaker / localisation / Bedrock work.

**Next action:** start **module 01** (simulation engine) with the agent prompt in `docs/modules/01_SIMULATION_ENGINE.md` §12. Module 09 step 1 (static SVG network in mock mode) can run in parallel.

**Git:** the human manages branches and commits. Nothing has been committed by agents.

## 2. Module status

| # | Module | Gate | Tier | Status | Next step |
|---|---|---|---|---|---|
| — | shared/contracts + units + ids | all | T1 | **done** (`backbone/1.1.0`) | — |
| 01 | [Simulation engine](docs/modules/01_SIMULATION_ENGINE.md) | G1 | **T1 core** | approach validated (`make feasibility`); code = stubs | step 1 |
| 02 | [Data generation](docs/modules/02_DATA_GENERATION.md) | G2 | T1 | stubs | after 01 |
| 04 | [ML predictor](docs/modules/04_ML_PREDICTOR.md) | G4 | T1 | stubs | after 02 |
| 05 | [Detector (+ localisation T2c)](docs/modules/05_ANOMALY_LOCALISATION.md) | G5 | T1 / T2c | stubs | after 04 |
| 07 | [Explanation: template (+ Bedrock T2d)](docs/modules/07_AQUAAGENT_BEDROCK.md) | G7 | T1 / T2d | stubs | step 1 anytime |
| 08 | [Orchestrator API](docs/modules/08_ORCHESTRATOR_API.md) | G8 + **MVP** | T1 | stubs | steps 1–2 after 01 step 7 |
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
