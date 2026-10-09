# TILL_NOW.md — build status log

> What has been done, what is next, and where everything lives.
> **Update rule (INSTRUCTIONS.md §8):** every agent appends to the Progress log and updates Module status at the end of every step, with evidence. Facts only.
> Contract: `backbone/1.1.0` ([BACKBONE.md](BACKBONE.md)). Process: [INSTRUCTIONS.md](INSTRUCTIONS.md). Runbook: [docs/RUNBOOK.md](docs/RUNBOOK.md).

---

## 1. Current state at a glance (2026-10-08)

**Phase:** modules 01 (G1) and 02 (G2) done; orchestrator skeleton + blueprint frontend done. **AWS (ap-south-1) live:** sim image in ECR and **ds1 (1,200 sims, 0 failed) generated on Fargate Spot into S3** `s3://aquaagent-<acct>-ap-south-1/processed/ds1/`. Nothing runs while idle.

**Build focus (BACKBONE §2, v1.1.0):** T1 = the **local MVP detection loop**: simulation → dataset → MLP → residual detector → challenge → template explanation → SVG UI. Gate **MVP** must pass before any AWS / SageMaker / localisation / Bedrock work.

**Next action:** module 04 (predictor: features from ds1 → baseline + MLP, leakage tests), then 05 (detector) → 07 template → 08 steps 3–7 (MVP). SageMaker training (06) uses `features/ds1/` in the same bucket. RL (T3) trains against the sim container as its environment, not a fixed dataset.

**Git:** branch `Predictor_Model` (predictor work). Earlier: `simulation`. Commits are made per step after the lead's review (owner request, 2026-10-08). No pushes.

## 2. Module status

| # | Module | Gate | Tier | Status | Next step |
|---|---|---|---|---|---|
| — | shared/contracts + units + ids | all | T1 | **done** (`backbone/1.1.0`) | — |
| 01 | [Simulation engine](docs/modules/01_SIMULATION_ENGINE.md) | G1 | **T1 core** | **done (G1 passed)** — 8 steps, last = step 8 (container + smoke + docs) | — |
| 02 | [Data generation](docs/modules/02_DATA_GENERATION.md) | G2 | T1 | **done (G2)** — ds1 in S3 | — |
| 04 | [ML predictor](docs/modules/04_ML_PREDICTOR.md) | G4 | T1 | **done (G4 ticked with evidence)** — ship model `mlp_ds1_202610090559` (MLP; GNN kept as research artifact); `model.tar.gz` in S3; BI-25, BI-26 OPEN | 05 detector uses `predict()` LOO residuals + σ from `metrics_val.json` |
| 05 | [Detector (+ localisation T2c)](docs/modules/05_ANOMALY_LOCALISATION.md) | G5 | T1 / T2c | stubs | after 04 |
| 07 | [Explanation: template (+ Bedrock T2d)](docs/modules/07_AQUAAGENT_BEDROCK.md) | G7 | T1 / T2d | stubs | step 1 anytime |
| 08 | [Orchestrator API](docs/modules/08_ORCHESTRATOR_API.md) | G8 + **MVP** | T1 | **steps 1–2 done** (skeleton + stale-session recovery) | step 3 after module 04 |
| 09 | [Frontend](docs/modules/09_FRONTEND.md) | G9 | T1 | **landing + live simulator + /city concept demo done** (steps 1–4, 6 partly); design system in `frontend/DESIGN.md` | step 5 (challenge/report/reveal) after 08 step 5 |
| 10 | [Demo and pitch](docs/modules/10_DEMO_AND_PITCH.md) | G10 | T1 | — | after MVP |
| 03 | [AWS infra](docs/modules/03_AWS_INFRA.md) | G3 | T2a | **partly run**: 00–04, 05 (sim only), 06, 07 | 08–11, 15 after MVP |
| 06 | [SageMaker](docs/modules/06_SAGEMAKER.md) | G6 | T2b | **parked (owner, 2026-10-09):** training stays local (small scale); launcher ready (dry-run OK); Spot quota case still open (no cost) | only if training needs to scale up |

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
- [ ] **Move the predictor to PRODUCTION when the API orchestrator / gateway (module 08 + T2a) is deployed** (owner, 2026-10-09). Today it is validated only as a one-off ECS **test** task (`infra/scripts/16_serve_test_task.sh`, no ALB, operator-IP-only SG). Production path: `05_build_push_images.sh` (all 3 images at a commit SHA) → `08_network_alb.sh` → `11_ssm_params.sh` (set `AQUA_PREDICTOR_VERSION=mlp_ds1_202610090559`) → `09_ecs_service.sh` using `infra/ecs/task-definition.json.tpl` (already has the `predictor` container + `AQUA_PREDICTOR_URL=http://localhost:8001` for the api, 1 vCPU / 3 GB). Then the api `PredictorClient` calls `POST /predictor/predict`. Budget: ALB ≈ $17/mo idle → park/teardown outside demo windows.
- [ ] Accept/reject BI-25 (virtual sensors for the placement experiment) and BI-26 (predictor as its own container, new env `AQUA_PREDICTOR_URL`) and fold into BACKBONE.
- [ ] SageMaker Spot quota request (case open) — harmless; cancel or keep for later scale-up.
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
| 2026-10-08 | 08 | steps 1–2 orchestrator skeleton | done | api/app, api/clients/sim_client.py, api/session/*, api/routes/*, api/tests/test_api_skeleton.py | 16 api tests; live: tap T2 → node 4 demand 3.83 → 8.83 L/s next step | `46c65ca`, `5e1cc85` (auto-recovery of a stale sim session); challenge/agent routes return 501 until step 5 / module 07 |
| 2026-10-08 | 09 | phase 1 landing + simulator UI | done | frontend/src/** (pages, components, store, client, blueprint.css, WebGL background) | tsc + build + no-hydraulics pass | `97dc552`; copy rewritten to true/measured claims only (§16) |
| 2026-10-08 | 09 | phase 2 live wiring + fixtures | done | frontend/src/api/fixtures, scripts/record_fixtures.mjs, scripts/check-no-truth-fields.sh | headless run vs live API: 5×, tap, pipe-4 leak droplets, V1 close, reset; 0 console errors | `e88209f`; mock replays 21 recorded frames; pipe-4 shows ≈0 flow at some ticks with a mid-pipe leak — real physics (upstream half per §7.4), not a bug |
| 2026-10-08 | stack | containers end to end | done | docker-compose.yml, Makefile | sim + api containers + frontend: /api/health ok, step 20 → 01:40, S1/S2/S3 46.15/44.32/44.19 m | podman here: `make compose-up` falls back to `uvx podman-compose`; stop stray native servers first (ports 8000/8080) |
| 2026-10-08 | 09 | darker background, /city concept demo, DESIGN.md | done | frontend/src/components/BlueprintBackground.tsx, src/pages/City.tsx, frontend/DESIGN.md, INSTRUCTIONS.md (reading row 7) | lint + build pass; hero worst-case contrast white 5.6:1, #e0f2fe 4.9:1; City lazy chunk 15 kB | dots removed, ground #035a8c; /city is a labelled CONCEPT DEMO (illustrative values, no real org/person names, links to /simulate) |
| 2026-10-08 | 09 | smooth transition into /city | done | frontend/src/components/CityLink.tsx, src/styles/blueprint.css, src/pages/City.tsx, frontend/DESIGN.md | lint + build pass; headless: click → /city, transition attr cleared, 0 console errors | `53392e1`; View Transitions circular reveal from click point, chunk preloaded on hover, fade fallback, off under reduced motion |
| 2026-10-08 | 02 | data generation (all steps) | done (G2) | sim/scenarios/*, sim/generate/*, sim/cli.py, config/generation/ds1.yaml, 7 test files | ~86 sim+api tests; 0.47 s/sim; repro: identical SHA-256; real-S3 smoke ok | `357f5fc`; holdout applies to LEAK/BURST faults; values rounded to fixed resolution (WNTR solver jitter 1e-13); LARGE leak median 24.5% sits at the 25% bucket edge (ranges unchanged) |
| 2026-10-08 | 03 | AWS foundation in ap-south-1 | done | infra/scripts (02 lifecycle, 05 --only, 06 subnets/SLR/Spot, 07 Spot) | budget $10/mo; bucket versioned+private+lifecycle; 4 roles (sim-task: write-only data, no Bedrock/SageMaker/delete); ECR; ECS cluster FARGATE+FARGATE_SPOT | `585126f`; D1 = ap-south-1 (Bedrock via global inference profiles); default VPC had no subnets → recreated default subnets |
| 2026-10-08 | 02/03 | ds1 on AWS | done | ECR aquaagent-sim:357f5fc (267 MB); task def aquaagent-datagen:1 | 4 shards + merge on FARGATE_SPOT ≈ 8.5 min; manifest n_valid 1200 / n_failed 0; splits 837/179/184; 90 MB in processed/ds1 | idle cost ≈ ECR $0.03/mo + S3 <$0.01/mo; no running tasks |
| 2026-10-09 | 04 | steps 1–2 features + scalers + online path | done | ml/features/{builder,scalers,tensorize}.py, Makefile (`features`, `eval-predictor`) | `make features`: train 241,893 rows / 837 sims (181,851 normal), val 51,731, test 53,176; `pytest ml/tests` 22 passed (offline == online ±1e-6) | predictor targets HEAD (pressure = head − elevation); virtual sensors for placement experiment = BI-25 (OPEN, docs/modules/04 §13 P-04-1) |
| 2026-10-09 | 04 | steps 3–6 baseline, MLP, GNN, train.py, predict(), leakage tests | done | ml/predictor/{baseline,masking,mlp,gnn,train,predict,evaluate}.py, ml/evaluation/{hop_error,metrics}.py, ml/tests/{test_leakage,test_predict_parity}.py | MLP 144k params, best epoch 54, 396 s; GNN (edge-aware GATv2, 4 layers, 4 heads, pure torch) 160k params, best epoch 38, 1,370 s (local CPU); shuffled-target test passes (≥ 3×); LARGE_LEAK val LOO max\|z\| > 3 in 22/22 sims (MLP and GNN) | training mask mix: 50% contract layout (0–1 of 5 sensors hidden), 50% random k = 1..5 pressure sensors; held-out placements 3-5-7, 2-5-7 |
| 2026-10-09 | 04 | step 7 test evaluation (once) | done | data/experiments/eval_{val,test}_202610090559/ (metrics.json, coverage.csv, hop_error.csv, placements.csv, plots/) | **test, contract layout, hidden junctions 3/5/7, normal rows (stride 2, n = 60,234 node-steps, 184 sims): baseline MAE 1.932 m, MLP 0.165 m, GNN 0.162 m** (RMSE 2.83 / 0.74 / 0.76; §9.5 target < 1.0 m met); coverage k = 1→5: baseline 2.75→1.00 m, MLP/GNN flat 0.105–0.112 m; hop 1/2/3: GNN 0.110/0.106/0.116 m; held-out k=3 placements GNN 0.058 m vs seen 0.115 m | **finding:** with SCADA context (tank level, pump flow, time) the state is nearly determined — val k = 0 (no pressure sensors, OOD) GNN 0.099 m; residual error is node 5 / DEMAND_SHIFT. GNN ≈ MLP on this fixed topology (§9.1 expectation). Coverage/hop curves are flat on ds1 → research question needs a larger network / node-level demand variability |
| 2026-10-09 | 06 | step 1 values + launcher | partial (blocked) | ml/sagemaker/launch_training.py, infra/env.sh (local, gitignored) | image resolved via SDK: pytorch-training 2.8.0-cpu-py312 (ap-south-1); staged source runs with SM_* env and no repo on path; features in s3://…/features/ds1/; IAM simulate CreateTrainingJob/PassRole allowed | **every SageMaker training instance quota = 0 in this account**; Spot ml.m5.xlarge increase to 5 requested (min allowed > AWS default 4), status CASE_OPENED. Owner override of tier rule: SageMaker training requested before gate MVP |
| 2026-10-09 | 04 | ship model + packaging | done | ml/predictor/package.py, ml/predictor/predict.py (`resolve_artifact`: dir / tar.gz / s3://) | `mlp_ds1_202610090559` (MLP) chosen per D4: test hidden-junction MAE 0.165 m (GNN 0.162 m), lower LOO σ S1–S3 0.055/0.088/0.119 m vs GNN 0.057/0.097/0.130 m, `predict()` p50 1.8 ms / p95 2.4 ms (GNN 5.6 / 7.3 ms); model.tar.gz 542 kB → s3://…/models/predictor/mlp_ds1_202610090559/ (+ gnn_ds1_202610090559, experiments/<mv>/) | G4 checklist ticked in docs/modules/04 §9 |
| 2026-10-09 | 04 | predictor service container (BI-26) | done | ml/serve/{app.py,Dockerfile,requirements.txt,smoke.py}, ml/tests/test_serve.py | `pytest ml/tests` 28 passed; local container vs in-process max\|Δ\| 0.0 over 54 windows, HTTP p50 35 ms / p95 54 ms; 422 on ground-truth fields, 409 on wrong model_version; image 1.08 GB (325 MB compressed) | routes `/predictor/health`, `/predictor/predict` (§7.9), `/ping`, `/invocations` (SageMaker-compatible) |
| 2026-10-09 | 03/04 | ECS test deploy (no ALB) | done | infra/scripts/{04,05,06}_*.sh (predictor repo/build/log group, `IMAGE_TAG` override), infra/scripts/16_serve_test_task.sh, infra/ecs/{task-definition,serve-test-task-definition}.json.tpl, infra/env.sh(.example) | ECR `aquaagent-{sim,api,predictor}:dev-202610090703` (sim retagged from 357f5fc, unchanged code); Fargate Spot test task: sim, predictor, api all RUNNING; predictor log `loaded predictor mlp_ds1_202610090559 from s3://…/model.tar.gz`, `/predictor/health` 200; **task stopped** (0 running) | remote §7.9 smoke (`16_serve_test_task.sh smoke`) NOT run — owner wrapped up first; run it on the next start. Images tagged `dev-*` because the tree was uncommitted |
