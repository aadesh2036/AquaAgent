# 02_DATA_GENERATION.md
Backbone version: backbone/1.1.0 | Gate: **G2** | Tier: **T1** | Est. effort: 7 h
Depends on: 01 (engine functions) | Blocks: 04, 05 | Schedule slot: Day 1 night (smoke + calibration) → Day 2 AM (full ds1) (BACKBONE §13)

## 1. Purpose
Turn the physics engine into a reproducible, validated, split-by-simulation dataset: `ds1`, 1,200 sims across the 8 scenario types of §8.1. The **operational variation** types (HIGH/LOW_DEMAND, DEMAND_SHIFT) are included so the detector cannot learn "pressure ↓ = leak". Truth (state tables) is kept strictly separate from what a model may see (`sensors` + `context`). Everything is generated **locally** (≈0.2 s per sim), and S3 upload is T2a.

## 2. Inputs — contracts consumed
- §7.1 `NetworkConfig`, §6.4 sensor layout, §7.2 `ScenarioSpec`
- §8.1 ds1 mix (`DS1_SCENARIO_COUNTS`), §8.2 locations, §8.3 noise, §8.4 validation, §8.5 splits + holdout (D9), §8.6 local batch execution
- §5.1 IDs, §5.2 two unit layers (observation = m, L/s), §5.3 300 s, §5.4 seeds + `config_hash`
- Module 01: `build_network(pipe_split_pos, demand_profile)`, `add_junction_leak`, `add_pipe_leak`, `to_snapshot`, `check_mass_balance`

## 3. Outputs — contracts produced
- §7.5 tables (`TABLE_COLUMNS`), §7.6 `manifest.json`
- Local layout mirroring §10.2: `data/raw/ds1/shard=i/<table>/part-*.parquet` → `data/processed/ds1/split=…/<table>/` + `data/processed/ds1/manifest.json` (T2a: `aws s3 sync` to the same keys)
- `config/generation/ds1.yaml` with **calibrated** leak-area ranges

## 4. Files owned
`sim/scenarios/` (`sampler.py`, `demand.py`), `sim/generate/` (`runner.py`, `noise.py`, `validation.py`, `writer.py`, `merge.py`, `calibrate.py`), `sim/cli.py` (`generate`/`merge` bodies), `config/generation/ds1.yaml`, `sim/tests/test_generate_*.py`, `sim/tests/test_splits.py`, `sim/tests/test_firewall_data.py`, `scripts/datagen_local.sh` (parallel shards).

## 5. Design decisions (binding)
- **Deterministic per simulation:** `seed = hash64(dataset_seed, sim_index)` (e.g. first 8 bytes of SHA-256 of both), `Generator(PCG64(seed))` for every draw, and `config_hash` per §5.4. Shard = `sim_index % num_shards`.
- **One network build per sim** with `pipe_split_pos` drawn per pipe (`U(0.2, 0.8)`), demand profile and operations applied, the fault from §8.1, then a 24-h EPS at 300 s.
- **ds1 = 8 types only** (§8.1). ds2 types are not sampled in T1. The sampler raises on them.
- **Noise and missing values only on `sensors.measured_value`**, never on `true_value`. Missing = null. Sensor faults are ds2.
- **Observation-layer units:** pressure m, flow L/s (`measurement` column says which), converted with `shared.units`.
- **Validation (§8.4)** on every sim. Failures go to `validation_log` only.
- **Splits:** by `simulation_id`, stratified by `scenario_type`, 70/15/15. **Holdout:** sims with a fault at `pipe:5` or `junction:6` → test only.
- `hop_to_nearest_sensor` computed on the canonical graph (from §6.2 + §6.4) and stored in `node_states`.
- **Deterministic Parquet:** fixed row order (sim, time, id), pyarrow with no timestamps in metadata. This makes the bit-for-bit G2 test possible.

## 6. Implementation plan
| # | Step (≤ 2 h) | Done when |
|---|---|---|
| 1 | `demand.py` diurnal profile (§7.2 fields, `global_mult`); `sampler.sim_seed`, `sample_scenario` for the 8 ds1 types; `plan_dataset(cfg)`. | Test: 500 specs per type validate as `ScenarioSpec`, ranges respected, same seed → identical JSON, counts == `DS1_SCENARIO_COUNTS`. |
| 2 | `runner.run_simulation(spec)` → all tables (state SI + sensors/context in observation units) using 01's builder; `noise.py`. | One NORMAL + one MEDIUM_LEAK sim → tables with exact `TABLE_COLUMNS`, 289 timesteps, noise applied only to `measured_value`. |
| 3 | `calibrate.py`: 14 locations × area grid → realised leak / mean system demand. Write final ranges + table to `ds1.yaml` (`calibration.done: true`). Preview (pipe 4) is in WNTR_FEASIBILITY §3. | ≥ 80% of 200 re-sampled leaks land in their intended `severity_bucket`. |
| 4 | `validation.py` (all `VALIDATION_CHECKS`) + `writer.py` + `cli generate --shard --num-shards --limit --out`. | `make datagen-local N=20` writes 20 sims; a NaN-injected sim is excluded and logged. |
| 5 | Reproducibility test (G2). | `pytest sim/tests/test_generate_repro.py`: two runs → identical Parquet SHA-256. |
| 6 | `merge.py`: union shards, `assign_splits`, holdout, `graph/`, `manifest.json` (wntr version, git sha, counts). `scripts/datagen_local.sh` runs N shards in parallel then merge. | Split-integrity + holdout tests green; manifest validates; full ds1 ≥ 95% valid; wall time recorded in TILL_NOW. |
| 7 | Firewall data test (§8). | `pytest sim/tests/test_firewall_data.py` green. |

## 7. AWS steps
T1: none. **T2a** (after gate MVP):
```bash
aws s3 sync data/processed/ds1 s3://$AQUA_BUCKET/processed/ds1/
aws s3 cp data/processed/ds1/manifest.json - | head        # sanity (local copy)
```
`infra/scripts/07_run_datagen.sh` (ECS RunTask) is T3 and only useful for much larger datasets.

## 8. Tests
- **Unit:** sampler ranges per type; demand profile; noise only on `measured_value`; validation exclusion; hop distances.
- **Contract conformance:** `ScenarioSpec`, `ScenarioRow`, `DatasetManifest`; columns == `TABLE_COLUMNS`.
- **Reproducibility:** identical Parquet hashes for the same seed.
- **Split integrity:** no `simulation_id` in two splits; per-type split within ±2% of 70/15/15; holdout only in test.
- **Firewall (BACKBONE §11), `sim/tests/test_firewall_data.py`:** (a) `sensors` + `context` contain no `FORBIDDEN_INPUT_COLUMNS` except `sensors.true_value` (which module 04 must drop); (b) no `LK_*`/`_B` id in any table except inside `scenarios.spec_json`; (c) `measured_value ≠ true_value` where σ > 0; (d) hidden nodes (3, 5, 7) never appear in `sensors`.

## 9. Acceptance gate — G2
- [ ] 20-sim local smoke run reproducible bit-for-bit from seeds
- [ ] leak-size calibration recorded (`config/generation/ds1.yaml`)
- [ ] full `ds1` (1,200) in `data/processed/ds1/` with manifest (T2a: also in S3)
- [ ] ≥ 95% valid
- [ ] split integrity test; holdout locations absent from train/val
- [ ] (module) firewall data test green; counts per type match §8.1 minus failures

## 10. Risks and fallbacks
- Burst convergence failures: clamp, log, and count in `n_failed`.
- Buckets not separable at some locations: report the realised distribution honestly (§16).
- Module 01 cut pipe leaks (end of Day 1): pipe scenarios become junction leaks at the downstream junction. Note it in the manifest + TILL_NOW.

## 11. Handoff
- To **04**: `data/processed/ds1/` + manifest; observation units; `hop_to_nearest_sensor`; `PREDICTOR_TRAIN_SCENARIOS` filtering is 04's job.
- To **05**: val/test + labels (`is_anomalous`, `severity_bucket`, `fault_start_s`), `OPERATIONAL_SCENARIOS` for FAR.
- To **08**: the noise model (same σ applied to live readings) and `ds1.yaml` leak ranges for challenge difficulty.
- To **10**: dataset size, test-sim counts, holdout definition.

## 12. Agent prompt
```
You are implementing module 02 (Data Generation) of AquaAgent.
Read, in order and completely: INSTRUCTIONS.md, BACKBONE.md, docs/modules/02_DATA_GENERATION.md,
TILL_NOW.md. Read nothing else; use module 01 only through the functions in §2/§11.
Implement §6 in order, one step at a time; after each run its "done when" check plus
`make lint && make contracts-test && .venv/bin/python -m pytest sim/tests`, update TILL_NOW.md, STOP.
Only edit files in §4. ds1 = the 8 types in DS1_SCENARIO_COUNTS. All randomness via numpy
Generator(PCG64(seed)). Noise only on measured_value. Split by simulation_id; holdout pipe:5, junction:6 →
test only. The firewall data test is mandatory. Generate locally; S3 upload is T2a.
If a contract is wrong, write it under §13 and stop. Do not create git branches or push.
```

## 13. Proposed Backbone Changes
_(empty)_
