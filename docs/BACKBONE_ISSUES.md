# BACKBONE_ISSUES.md — resolution log

All issues found in `backbone/1.0.0` are **resolved in `backbone/1.1.0`** (2026-10-08). The research and measurements behind them are in [docs/research/WNTR_FEASIBILITY.md](research/WNTR_FEASIBILITY.md).
Guiding rule from the owner: *one small feature that works beats five almost working*. The simulation is the core, and the build focuses on the basic detection loop (BACKBONE §2).

New issues go at the bottom with status **OPEN** and are handled per BACKBONE §17 / INSTRUCTIONS §6.

| ID | Sev | Problem (1.0.0) | Resolution in 1.1.0 | Where |
|---|---|---|---|---|
| BI-01 | H | 60 s interactive vs 300 s dataset cadence → lag/window/detector constants meant different things in training and in the live demo | **Single 300-s cadence everywhere.** Speed 1×/5×/20× = 1/5/20 steps per tick. Measured 18 ms per step, so even 20× fits in the 1-s tick | §5.3, §7.8, D6 |
| BI-02 | H | Flow residuals needed predicted flows that §7.9 did not return | **`leave_one_out_flow`** `{F1,F2: {predicted_lps, observed_lps}}`. The same LOO masking as pressure, over all 5 sensors, so there is one mechanism and no separate heads | §7.9, §9.1–9.2, contracts |
| BI-03 | H | Signatures (raw Δobserved) and online z-scores lived in different spaces | Signatures are built **through the same predictor + residual pipeline** (z-space) and record the predictor version. Localisation moves to **T2c** | §9.4 |
| BI-04 | H | API Gateway HTTP API has a hard 30-s timeout; a 6-turn Bedrock loop can exceed it | **T1 uses the instant TemplateReporter.** T2d Bedrock has a 20-s server budget, then falls back to the template. HTTP API kept (the limit is not adjustable, per AWS docs) | §7.14.1, §9.6, §3.2 |
| BI-05 | H | Newer Claude models need inference profiles; IAM covered only the model | `AQUA_BEDROCK_MODEL_ID` may be an inference-profile ID. IAM allows the profile ARN plus foundation-model ARNs in all routed regions. Discovered by `14_bedrock_check.sh` | §10.1, §10.3, §10.4 |
| BI-06 | M | DEMAND_SPIKE was labelled anomalous but treated as a false-alarm risk | DEMAND_SPIKE moves to ds2 (T3). Rule fixed for later: it is a hydraulic event, reported in its own row, never in leak recall or FAR. **FAR = alarms on {NORMAL, HIGH/LOW_DEMAND, DEMAND_SHIFT}** | §8.1, §9.5 |
| BI-07 | M | §5.2 SI rule vs L/s in sensors/context; suffix-less `true_value`/`value` | **Two layers:** state layer SI, observation layer SCADA units (m, L/s); `measurement`/`unit` column carries the unit | §5.2 |
| BI-08 | M | `_pct`, `_lpm` undefined | Added to the §5.2 unit table | §5.2 |
| BI-09 | M | Scalers stored in two places | `features/ds1/scalers.json` is the source; a **copy inside `model.tar.gz`** is the only one inference reads | §7.7, §10.5 |
| BI-10 | M | Exec role lacked SSM read; CodeBuild role missing | Exec role gets `ssm:GetParameters` + `kms:Decrypt` via SSM; optional `aqua-codebuild` role | §10.3 |
| BI-11 | M | `sim` container shares the api task role | Accepted and documented. The sim never calls AWS (test in module 01) | §10.3 |
| BI-12 | M | Duplicate CORS owners | **FastAPI owns CORS**; API Gateway CORS unset; `OPTIONS` exempt from the API key | §3.2, §7.14.1 |
| BI-13 | M | API key visible in the browser | Documented as a deterrent; API Gateway stage throttling on | §7.14.1, §10.5 |
| BI-14 | M | Grounding "every number" ambiguous for IDs, clocks, ranks | Exempt: element IDs and `HH:MM` labels present in tool results, ranks/priorities 1–5; unit normalisation listed | §9.6 |
| BI-15 | L | Missing ID formats | `inc_<sessionShort>_<t>`, `chl_…`, `thr_<ds>_<ts>`, `sig_<ds>_<ts>` | §5.1, `shared/contracts/ids.py` |
| BI-16 | L | Fault/scenario naming mismatches | Mapping fixed (`SCENARIO_TO_FAULT`). PUMP_TRIP stays reserved for ds2 | §8.1 |
| BI-17 | L | Challenge difficulty → leak size undefined | small/medium/large → SMALL/MEDIUM/LARGE_LEAK ranges in `ds1.yaml`; default medium; locations exclude sensor junctions; fault starts 1–3 steps after start | §7.14.1, §8.2 |
| BI-18 | L | Handoff document missing | Added as `CONTEXT/AquaAgent_handoff.md`; its §22 visual direction is used in module 09 | §0.5 |
| BI-19 | L | Reading list said "two files" | §0.1 lists `INSTRUCTIONS.md` + BACKBONE + module MD (+ `TILL_NOW.md` for status) | §0.1 |
| BI-20 | L | `pump_status` had three representations | Layered: state `OPEN/CLOSED`, observation `0/1`, UI `ON/OFF`, via `shared/units` | §5.2 |
| **BI-21** | **H** | **New:** no official `.inp` of the EPA tutorial exists; 1.0.0 said "load the tutorial `.inp`" and refused to state connectivity | Connectivity, zones and UI coordinates are **stated once in §6.2** (transcribed from EPANET 2.2 Fig. 2.1). Module 01 builds from it, exports `.inp`/`.json`, and tests equality | §6, §6.2 |
| **BI-22** | **H** | **New:** WNTR 1.5.0 ships wheels for Python 3.10–3.13 only; the dev laptop runs 3.14 | **Python 3.12 everywhere** (`make setup` uses `uv`; containers `python:3.12-slim`); `wntr==1.5.0` pinned | §5.5, D11, D12 |
| **BI-23** | M | **New:** pipe leaks via `split_pipe` mid-run change topology (risk §14) | **Pre-split** every candidate pipe when the model is built (zero-demand `LK_<pipe>`, measured ΔP ≤ 1.7e-5 m). A leak is `add_leak` on an existing node | §6.3 |
| **BI-24** | M | **New (scope):** 1.0.0 put SageMaker, Bedrock, localisation and ECS datagen on the T1 critical path | Re-tiered: **T1 = local detection loop + gate MVP**. T2a AWS deploy → T2b SageMaker → T2c localisation → T2d Bedrock. ds1 cut to 1,200 sims / 8 types | §2, §12, §13 |

## Open issues
_None._ New ones go here as `BI-25…` with: section, problem, proposed fix, impact, and status OPEN.
