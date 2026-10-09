# 04_ML_PREDICTOR.md
Backbone version: backbone/1.1.0 | Gate: **G4** | Tier: **T1** (baseline + MLP) / T3 (GNN) | Est. effort: 8 h
Depends on: 02 (processed ds1) | Blocks: 05 (residuals), 08 (in-process predictor), 06 (T2b) | Schedule slot: Day 2 AM–PM (BACKBONE §13)

## 1. Purpose
Learn "what the network should look like right now" from 3 pressure sensors, 2 flow sensors and SCADA context. The model reconstructs hidden-node pressures and, by masking one sensor at a time, predicts each of the **5 sensors** from the others (leave-one-out). It is trained **only on hydraulically normal states**, so leaks show up as residuals. The same `train.py` runs locally (T1) and in SageMaker (T2b).

## 2. Inputs — contracts consumed
- §7.5 tables from `data/processed/ds1/`: **inputs only from** `sensors.measured_value`, `context`, `graph`; **targets** from `node_states.pressure_m` (scored nodes) and `sensors.true_value` of F1/F2 (flow targets for flow LOO, observation units L/s)
- §7.6 manifest, §7.7 `GraphSample` + frozen feature orders, flattened MLP layout, §7.8 `SensorWindow`, §7.9 response incl. `leave_one_out_flow`
- §9.1 (normal-only, 5-sensor masking, model ladder), §9.2, §9.5, §11, §5.3 (300 s; lags 300 s / 900 s)
- `shared.contracts.models`: `PREDICTOR_TRAIN_SCENARIOS`, `PRESSURE_SENSORS`, `FLOW_SENSORS`, `NODE_FEATURES_V1`, `FORBIDDEN_INPUT_COLUMNS`

## 3. Outputs — contracts produced
- `data/features/ds1/{train,val,test}.pt` + `scalers.json` (mirrors §10.2 `features/`)
- `data/models/predictor/<model_version>/` = `model.pt`, `scalers.json` (copy), `meta.json` (feature order, sensor layout, model version), packaged as `model.tar.gz` (layout ready for 06)
- `data/experiments/<model_version>/{metrics.json, hop_error.csv, plots/}`
- **`ml.predictor.predict.load_artifact(dir)` + `predict(window, artifact, model_version) -> PredictorResponse`**, the single inference function used by 05, 08 (T1 in-process) and 06 (T2b `inference.py`)

## 4. Files owned
`ml/features/` (`builder.py`, `scalers.py`), `ml/predictor/` (`baseline.py`, `mlp.py`, `train.py`, `predict.py`, `gnn.py` T3), `ml/evaluation/hop_error.py`, `ml/evaluation/metrics.py::predictor_metrics`, `ml/tests/test_features_*.py`, `ml/tests/test_leakage.py`, `ml/tests/test_predict_*.py`, `ml/requirements.txt`, `ml/README.md`.

## 5. Design decisions (binding)
- **Normal-only training (§9.1):** whole episodes of `PREDICTOR_TRAIN_SCENARIOS` plus **pre-fault timesteps** (`sim_time_s < fault_start_s`) of leak sims, train split only. *Rejected:* training on leaks (the residuals collapse).
- **One flattened MLP (T1 ship model):** input = 3 pressures + 2 flows (standardised; 0 when masked) + 5 mask bits + lags (300 s, 900 s) for the 5 sensors + context (tod sin/cos, tank level, pump on, pump flow, reservoir head). Output = pressure at every scored node (junctions 2–7 + tank 8) **plus F1, F2 flow**. Loss = MSE on the scored targets (pressure, and flow on its own scale).
- **Random masking:** each sample hides 0 or 1 of the 5 sensors (uniform over {none, S1, S2, S3, F1, F2}). The masked sensor's value is replaced by 0 + mask bit 0, and its true value stays a target. At inference, `predict()` builds **6 rows in one batch** (no mask + each sensor masked) → `reconstruct` + `leave_one_out` + `leave_one_out_flow`.
- **Lags at the single 300-s cadence** (§5.3): lag1 = previous step, lag3 = 3 steps back. The window builder supplies ≤ 12 steps, and missing lags are masked.
- **Scalers** fitted on train only, saved to features and copied into the artifact. Inference reads the artifact copy only.
- **Ladder:** nearest-sensor + elevation-corrected baseline first (no training) → MLP. GNN is **T3**. D4: ship the MLP if it beats the baseline, else ship the baseline.
- **`train.py` is SageMaker-compatible** (`SM_CHANNEL_TRAIN`, `SM_CHANNEL_VAL`, `SM_MODEL_DIR`, `SM_OUTPUT_DATA_DIR` with local defaults), CPU, seeded (torch + numpy).

## 6. Implementation plan
| # | Step (≤ 2 h) | Done when |
|---|---|---|
| 1 | `make setup-ml`. `builder.py`: read only `sensors`(measured)/`context`/`graph` for inputs, targets from `node_states` + `sensors.true_value`; 300-s lags; normal-only filter for train; write `.pt`. | `make features` writes train/val/test; test asserts the read column set ∩ `FORBIDDEN_INPUT_COLUMNS` == ∅ (except targets read in a separate function). |
| 2 | `scalers.py` (train-only) + online path `window_to_features(SensorWindow, scalers, mask_sensor)`. | Offline == online features for the same timestep (±1e-6). |
| 3 | `baseline.py` + `hop_error.py`; val metrics. | `data/experiments/baseline_ds1_*/metrics.json` + `hop_error.csv`. |
| 4 | `mlp.py` + `train.py` (masking, flow targets, early stopping on val). | `make train-local` writes the artifact dir + `model.tar.gz`; val MAE printed. |
| 5 | `predict.py`: `load_artifact`, `predict` (6-row batch) → `PredictorResponse`. | `PredictorResponse.model_validate(predict(example_window, …))` passes; LOO keys == S1–S3, flow LOO keys == F1–F2. |
| 6 | Leakage tests + residual sanity (§8). | `pytest ml/tests/test_leakage.py` green. |
| 7 | Test-set evaluation once; hop table; per-type MAE. | MLP beats baseline on hidden-node MAE (else the D4 fallback is recorded); numbers in `metrics.json` + TILL_NOW. |

## 7. AWS steps
T1: none. T2a: `aws s3 sync data/features/ds1 s3://$AQUA_BUCKET/features/ds1/` and upload `model.tar.gz` to `models/predictor/<mv>/`. T2b: module 06 runs the same `train.py` on SageMaker.

## 8. Tests
- **Unit:** feature order frozen; lag cadence 300 s; masking distribution; scaler round-trip; baseline sanity; `predict` batch shape.
- **Contract conformance:** `PredictorResponse` from `predict()`; `meta.json` feature list == contracts.
- **Leakage (G4, BACKBONE §11) — `ml/tests/test_leakage.py`:**
  1. Shuffled hidden-node targets → val MAE ≥ 3× the real model.
  2. The builder never reads a forbidden column. Adding one to the raw table leaves the tensors bit-identical.
  3. No training row comes from post-fault timesteps, from leak types after `fault_start_s`, or from val/test.
  4. `predict()`/`window_to_features()` accept only `SensorWindow` (a `HydraulicSnapshot` raises).
  5. Residual sanity: on LARGE_LEAK val sims, max |z| (LOO residual / val-normal σ) after fault start > 3 for ≥ 90% of sims.

## 9. Acceptance gate — G4
Evidence: `data/experiments/{eval_val,eval_test}_202610090559/`, `data/experiments/mlp_ds1_202610090559/`, `pytest ml/tests` (2026-10-09).
- [x] MLP beats nearest-sensor baseline on hidden-node MAE — test, contract layout, hidden junctions 3/5/7: MLP 0.165 m vs baseline 1.932 m (GNN 0.162 m). Ship model = MLP `mlp_ds1_202610090559` (D4; lower LOO σ than GNN, 3× faster)
- [x] hop-distance table produced — `hop_error_{val,test}.csv` (+ by k), all C(6,k) placements
- [x] scalers fitted on train only — `ml/features/scalers.py` (train split, normal rows)
- [x] leakage tests pass — `ml/tests/test_leakage.py` (shuffle ≥ 3×, explicit allowed columns, masked inputs bit-identical, normal-only rows, disjoint splits)
- [x] LOO residual on LARGE_LEAK val sims > 3σ — 22/22 sims (100%) for MLP and GNN
- [x] (module) §9.5 predictor MAE reported honestly (incl. flat coverage/hop curves and k = 0 ablation, TILL_NOW 2026-10-09); `train.py` runs unchanged with `SM_*` env vars (staged run verified; no SageMaker job — quota 0, owner chose local training)

## 10. Risks and fallbacks
- Learns to reconstruct leaks → normal-only filter + test 5.
- MLP ≈ baseline: still fine for detection; ship the better one (D4). Never block the MVP.
- Train/serve skew: the single cadence + offline/online parity test.

## 11. Handoff
- To **05**: `predict()`; val residuals for σ; model version.
- To **08**: `load_artifact` + `predict` for the in-process `PredictorClient` (T1 default); artifact path.
- To **06 (T2b)**: `train.py`, `predict.py`, artifact layout.
- To **10**: metrics, hop table, the baseline-vs-MLP numbers.

## 12. Agent prompt
```
You are implementing module 04 (ML Predictor) of AquaAgent.
Read, in order and completely: INSTRUCTIONS.md, BACKBONE.md, docs/modules/04_ML_PREDICTOR.md, TILL_NOW.md.
Read nothing else for context.
Implement §6 in order; after each step run its "done when" check plus
`make lint && make contracts-test && .venv/bin/python -m pytest ml/tests`, update TILL_NOW.md, STOP.
Only edit files in §4. Inputs ONLY from sensors.measured_value, context, graph; train ONLY on normal states of
the train split; scalers on train only; single 300-s cadence; leave-one-out over all 5 sensors via one
6-row batch. train.py must run identically locally and with SageMaker SM_* env vars. Leakage tests are
mandatory. Report metrics exactly as measured. If a contract is wrong, write it under §13 and stop.
Do not create git branches or push.
```

## 13. Proposed Backbone Changes

### P-04-2 — Predictor served as its own container in the ECS serve task (BI-26, OPEN)
See docs/BACKBONE_ISSUES.md BI-26. Code: `ml/serve/` (app, Dockerfile, smoke). Test deploy: `infra/scripts/16_serve_test_task.sh`.

### P-04-1 — Virtual sensors + variable sensor placement for the predictor (BI-25, OPEN)
- **What:** training samples mix (a) the contract layout S1–S3 + F1/F2 with 0–1 sensor hidden (the §9.1 masking, unchanged) and (b) random placements of k = 1..5 pressure sensors over junctions 2–7 (F1/F2 each present w.p. 0.5). For (b), readings at nodes outside the default layout are *virtual*: `pressure_m + N(0, pressure_sigma_m)` from the same seeded noise model as ds1 (§8.3). Two k = 3 placements (`3-5-7` = alt layout A, `2-5-7`) are never sampled in training and are reported as unseen placements.
- **Why:** owner research question (2026-10-09): how reconstruction error grows as coverage drops and as targets move away from sensors, with a model that does not memorise one layout. ds1 has only one layout, in which every hidden junction is 1 hop from a sensor, so the question cannot be answered from `sensors.measured_value` alone.
- **Contracts touched:** §11 table (Dataset → model inputs) needs one sanctioned exception; §7.7 feature order, §7.8 `SensorWindow`, §7.9 are unchanged. GNN (§9.1 rung 3, T3) is trained alongside the MLP at the owner's request.
- **Safeguards:** features at uninstrumented nodes are exactly 0 (test `test_unobserved_values_never_reach_features`); default sensors use the recorded `measured_value` (test `test_default_sensor_inputs_equal_recorded_measured_value`); only normal train-split rows are trained on.
