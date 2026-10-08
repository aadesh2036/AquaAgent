# AquaAgent — Find the Water Nobody Can See

> Physics generates reality. ML reconstructs the hidden state. Anomaly detection finds what does not fit. An agent explains the evidence and recommends action.

**What.** This is a physics-grounded anomaly-detection prototype for a small pressurised water network (the EPA EPANET 2.2 tutorial network). It is observed by only **3 pressure sensors + 2 flow sensors**. The pipeline is: WNTR simulation → synthetic dataset in S3 → hidden-state predictor trained on SageMaker → residual-based detection and signature localisation → a grounded Bedrock agent that explains the evidence → FastAPI orchestrator → React SVG frontend on Amplify.

**Why.** We want to know whether a model can reconstruct a network's hidden hydraulic state well enough that *deviations* from it detect and localise a hidden leak, and whether an agent can explain that evidence **without inventing a single number** (BACKBONE §1.1). All of this is *in our simulated network, under stated assumptions* (§16).

> Status: **repository setup complete** (contracts, docs, stubs, feasibility-validated simulation approach). Module code is not implemented yet. See [TILL_NOW.md](TILL_NOW.md).
>
> **Build focus (T1 MVP):** simulation → dataset → MLP predictor → residual detector → challenge loop → template explanation → SVG UI, all running locally. AWS (S3/ECS/Amplify), SageMaker, localisation and the Bedrock agent follow in that order (BACKBONE §2).

## Start here
| You are… | Read |
|---|---|
| Any coding agent / contributor | [INSTRUCTIONS.md](INSTRUCTIONS.md) → [BACKBONE.md](BACKBONE.md) → your `docs/modules/NN_*.md` → [TILL_NOW.md](TILL_NOW.md) |
| Running things | [docs/RUNBOOK.md](docs/RUNBOOK.md), the linear terminal walkthrough (`make help` lists targets) |
| New to AWS / SageMaker / Bedrock | [docs/aws/](docs/aws/): 00 AWS · 01 SageMaker · 02 Bedrock · 03 CLI cheat-sheet · 04 teardown & cost |
| Reviewing the contract | [BACKBONE.md](BACKBONE.md) (frozen `backbone/1.1.0`) + [docs/BACKBONE_ISSUES.md](docs/BACKBONE_ISSUES.md) |

## Quickstart (local)
```bash
make setup            # Python 3.12 .venv via uv, wntr==1.5.0, .env / infra/env.sh templates
make feasibility      # reproduce the WNTR feasibility measurements
make contracts-test   # BACKBONE JSON examples ↔ Pydantic models; TS enum parity; units
make help             # all targets; unimplemented ones say "NOT IMPLEMENTED — see docs/modules/NN"
```

## Repository map
```
BACKBONE.md            master contract (schemas, IDs, units, endpoints, gates)
INSTRUCTIONS.md        process rules for every agent      TILL_NOW.md  build status log
shared/                contracts (Pydantic + TS twins), units, ids — the only schema code
config/                network (generated in G1), sensor layout, ds1 generation config
sim/                   aquaagent-sim: WNTR engine, scenarios, batch generate/merge, sim server   (modules 01, 02)
ml/                    features, predictor, anomaly, localisation, sagemaker, evaluation          (04, 05, 06)
api/                   aquaagent-api: FastAPI orchestrator, session, pipeline, Bedrock agent      (07, 08)
frontend/              React + TS + Vite + SVG (Amplify)                                          (09)
infra/                 AWS CLI scripts 00–15, 90, 99; IAM; ECS templates                          (03)
docs/                  modules/ (10 build plans), aws/ (primers), research/ (WNTR feasibility), RUNBOOK, BACKBONE_ISSUES, demo/
```

## Modules and gates
| # | Module | Gate | Tier |
|---|---|---|---|
| 01 | [Simulation engine](docs/modules/01_SIMULATION_ENGINE.md) | G1 | T1 |
| 02 | [Data generation](docs/modules/02_DATA_GENERATION.md) | G2 | T1 |
| 03 | [AWS infra](docs/modules/03_AWS_INFRA.md) | G3 | T2a |
| 04 | [ML predictor](docs/modules/04_ML_PREDICTOR.md) | G4 | T1 (GNN T3) |
| 05 | [Anomaly + localisation](docs/modules/05_ANOMALY_LOCALISATION.md) | G5 | T1 detector / T2c localisation |
| 06 | [SageMaker](docs/modules/06_SAGEMAKER.md) | G6 | T2b |
| 07 | [Explanation: template → Bedrock](docs/modules/07_AQUAAGENT_BEDROCK.md) | G7 | T1 template / T2d Bedrock |
| 08 | [Orchestrator API](docs/modules/08_ORCHESTRATOR_API.md) | G8 + MVP | T1 |
| 09 | [Frontend](docs/modules/09_FRONTEND.md) | G9 | T1 |
| 10 | [Demo and pitch](docs/modules/10_DEMO_AND_PITCH.md) | G10 | T1 |

## Results
_No results yet._ This section is generated from `experiments/` by `scripts/make_results_table.py` (module 10). Numbers are never typed by hand (§16).

## Honesty notes
- Simulated network and synthetic sensor data. This is not a real utility, and it does not represent any city.
- "Valve V1" is pipe 7's OPEN/CLOSED status, not an EPANET valve object (BACKBONE §6.2).
- External results cited in the briefing (AquaSentinel, Heter-GATRes) are *their* results on *their* benchmarks.
