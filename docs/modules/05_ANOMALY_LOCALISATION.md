# 05_ANOMALY_LOCALISATION.md
Backbone version: backbone/1.1.0 | Gate: **G5** | Tier: **T1 (detector)** / T2c (localisation) / T3 (sensor-fault rule, classifier) | Est. effort: 6 h (T1) + 4 h (T2c)
Depends on: 02 (val/test), 04 (`predict`), 01 (signatures, T2c only) | Blocks: 08 (in-process detector), 10 (metrics) | Schedule slot: Day 2 PM (detector, frozen) · Day 4 AM (T2c only after gate MVP) (BACKBONE §13)

## 1. Purpose
**T1:** turn predictor residuals into a decision with an RTCA-style dual-threshold detector (`NORMAL`/`WATCH`/`ANOMALY`). It is tuned on validation, then **frozen**, and its honest detection metrics include the false-alarm rate on operational variation. **T2c:** rank candidate pipes/junctions and a probable zone by physics signatures.

## 2. Inputs — contracts consumed
- §7.8 `SensorWindow`, §7.9 response (`leave_one_out` + `leave_one_out_flow`) via 04's `predict()`
- §7.5 val/test (`sensors`, `context`, `scenarios`), §7.6 manifest (holdout)
- §9.2 residuals/σ, §9.3 detector (k1 2.5, k2 3.0, W 6, T 3; 300-s steps), §9.5 targets, §8.1 `OPERATIONAL_SCENARIOS`
- T2c: §9.4 z-space signatures, §8.2 locations, §6.2 zones, module 01 builder
- IDs: `ids.thresholds_version`, `ids.signatures_version`

## 3. Outputs — contracts produced
- §7.10 `ResidualFrame`, `AnomalyResult`
- `data/models/anomaly/<thr_ds1_ts>/thresholds.json`: σ per sensor (S1–S3, F1–F2), k1, k2, W, T, predictor version, val metrics, content hash
- `data/experiments/<thr_ds1_ts>/{metrics.json, detection_table.csv}`: the §9.5 detection rows
- Python API for 08: `residual_frame(window, response, sigmas)`, `RTCADetector.from_thresholds_json(path)`, `.update(frame) -> AnomalyResult`, `.reset()`
- **T2c:** §7.11 `LocalisationResult`, `data/models/localisation/<sig_ds1_ts>/signatures.parquet`, `SignatureMatcher.rank(frames, top_k)`

## 4. Files owned
`ml/anomaly/` (`residuals.py`, `rtca.py`, `tune.py`; `sensor_fault.py`, `classifier.py` = T3), `ml/localisation/` (`signatures.py`, `matcher.py` = T2c), `ml/evaluation/metrics.py::{detection_metrics, localisation_metrics}`, `ml/tests/test_anomaly_*.py`, `ml/tests/test_localisation_*.py`.

## 5. Design decisions (binding)
- **Residuals:** `r_s = observed − LOO prediction` for S1–S3 (m) and F1–F2 (L/s); `z = r/σ`. σ = std of r on **val-normal** timesteps (operational types + pre-fault). Fixed σ, no adaptive EMA (it would absorb a slow leak).
- **RTCA (§9.3):** instant flag `|z| > k1`; cumulative flag `mean|z|` over the last W steps `> k2`; **ANOMALY** when ≥ 1 sensor has both flags for T consecutive steps; **WATCH** if instant-only; else NORMAL. `driving_sensors` = sensors flagged at confirmation; `anomaly_score` = squashed max cumulative |z| (document the formula).
- **Tuning on val only:** small grid over k1 ∈ {2, 2.5, 3}, k2 ∈ {2, 2.5, 3, 3.5}, W ∈ {3, 6, 9}, T ∈ {2, 3, 4}. Objective: max recall on MEDIUM/LARGE/BURST subject to FAR ≤ 5% on **each** operational type. **Freeze** = write `thresholds.json` + record its SHA-256 in TILL_NOW before any test evaluation.
- **FAR definition:** a sim counts as a false alarm if ANOMALY is ever confirmed on an operational sim. Reported per type (NORMAL, HIGH_DEMAND, LOW_DEMAND, DEMAND_SHIFT).
- **Detection delay:** steps from the true `fault_start_s` to `confirmed_time_s` (median for MEDIUM reported).
- **T2c localisation:** 14 locations × 3 sizes × 4 times of day → simulate (module 01), run through `predict` + `residual_frame`, average z over the detection window → signature. Online: cosine with every signature → max per location → softmax → ranked candidates; aggregate per zone. One signal space (z) online and offline. Holdout locations are in the dictionary by design.
- *T3:* SENSOR_FAULT rule and fault-type classifier (need ds2).

## 6. Implementation plan
| # | Step (≤ 2 h) | Done when |
|---|---|---|
| 1 | `residuals.py`: build `SensorWindow`s (≤ 12 steps, 300 s) from val/test `sensors`+`context`; call `predict`; `residual_frame`; `estimate_sigmas` on val-normal. | `ResidualFrame` validates; z on val-normal has \|mean\| < 0.2 and std ∈ [0.8, 1.2] per sensor. |
| 2 | `rtca.py` streaming detector + `AnomalyResult`. | Unit tests on synthetic z sequences: single spike → WATCH; sustained → ANOMALY after T; reset works. |
| 3 | `tune.py` grid on val → `thresholds.json` (`thr_ds1_<ts>`) + hash. **Freeze.** | File exists; hash recorded in TILL_NOW; FAR per operational type ≤ 5% on val (or the best achievable, reported). |
| 4 | Test evaluation once: recall by size, FAR per type, median delay, holdout-location recall. | `data/experiments/thr_ds1_*/metrics.json` + CSV; numbers with n copied to TILL_NOW. |
| 5 | Expose the Python API for 08; `from_thresholds_json`. | 08's pipeline test can import and run it on a recorded window. |
| 6 | **T2c only after gate MVP:** `signatures.py` (168 sims via 01) → `signatures.parquet` (`sig_ds1_<ts>`). | Deterministic from seed; records the predictor version. |
| 7 | **T2c:** `matcher.py` → `LocalisationResult`; test-set top-1/top-3, zone accuracy, holdout top-3. | Localisation rows of §9.5 reported. |

## 7. AWS steps
T1: none. T2a: upload `data/models/anomaly/` (and T2c `localisation/`) to `s3://$AQUA_BUCKET/models/…` and publish URIs with `AQUA_THRESHOLDS_URI=… AQUA_SIGNATURES_URI=… infra/scripts/11_ssm_params.sh`.

## 8. Tests
- **Unit:** z normalisation; RTCA state machine; tuning objective; (T2c) cosine/softmax ordering and zone aggregation.
- **Contract conformance:** outputs → `ResidualFrame`, `AnomalyResult`, `LocalisationResult`; version IDs match `ids` formats.
- **Freeze test:** `tune.py` never opens the test split (assert on paths read); test evaluation reads `thresholds.json` read-only and checks its hash.
- **Firewall:** `update()`/`rank()` take only `ResidualFrame`s; labels (`scenarios`) are read only in `metrics.py`.

## 9. Acceptance gate — G5
- [ ] thresholds tuned on val only and frozen (hash recorded) before test
- [ ] §9.5 detection rows produced on test (recall MEDIUM/LARGE/BURST, SMALL reported, FAR per operational type, median delay)
- [ ] FAR on operational-variation scenarios reported separately
- [ ] (T2c) localisation rows: top-1/top-3, zone accuracy, holdout top-3

## 10. Risks and fallbacks
- FAR too high on HIGH/LOW_DEMAND: raise k2/T. This is a predictor problem if z on operational sims is biased, so check per-type z means and feed back to 04.
- SMALL leaks undetectable at 3 sensors: report honestly (§9.5 expects lower).
- Thresholds accidentally tuned on test: freeze test + hash.
- **Cut line:** localisation is T2c. The demo reveal shows "detected + delay" without it.

## 11. Handoff
- To **08**: `residual_frame`, `RTCADetector` (+ thresholds path), and from T2c `SignatureMatcher`; W/T in 300-s steps.
- To **07**: meaning of `driving_sensors` and `anomaly_score` for the template wording.
- To **10**: `metrics.json` + CSV.

## 12. Agent prompt
```
You are implementing module 05 (Anomaly Detection; localisation is T2c) of AquaAgent.
Read, in order and completely: INSTRUCTIONS.md, BACKBONE.md, docs/modules/05_ANOMALY_LOCALISATION.md,
TILL_NOW.md. Read nothing else; use modules 01/04 only through the functions in §2/§11.
Implement §6 steps 1–5 in order (steps 6–7 only when TILL_NOW shows gate MVP passed); after each run its
"done when" check plus `make lint && make contracts-test && .venv/bin/python -m pytest ml/tests`, update
TILL_NOW.md, STOP. Only edit files in §4. Tune on VAL only; freeze thresholds.json and record its hash
BEFORE evaluating test. Report every metric as measured, with n. If a contract is wrong, write it under §13
and stop. Do not create git branches or push.
```

## 13. Proposed Backbone Changes
_(empty)_
