# 07_AQUAAGENT_BEDROCK.md
Backbone version: backbone/1.1.0 | Gate: **G7** | Tier: **T1 = TemplateReporter** · T2d = Bedrock agent · T3 = what-if/ask | Est. effort: 3 h (T1) + 6 h (T2d)
Depends on: shared contracts (`Incident`, `AgentReport`); 05 output semantics · T2d: 03 (IAM, `14_bedrock_check.sh`) | Blocks: 08 (`/agent/diagnose`), 09 (report panel), 10 | Schedule slot: Day 3 AM (template) · Day 4 AM (T2d, only after gate MVP and T2a–T2c) (BACKBONE §13)

> T2d readers: start with [docs/aws/02_BEDROCK_PRIMER.md](../aws/02_BEDROCK_PRIMER.md).

## 1. Purpose
Explain an `Incident` as WHAT / WHY / EVIDENCE / ACTION **without inventing a single number** (P3). **T1** does this deterministically with `TemplateReporter`, which is always grounded, instant and clearly labelled "template explanation". **T2d** upgrades it to a Bedrock Converse tool-use agent that is forced to answer through `submit_report`, grounding-checked with one retry, and falls back to the template.

## 2. Inputs — contracts consumed
- §7.12 `Incident` (no ground truth; `localisation` null until T2c), §7.10 `AnomalyResult`, §7.13 `AgentReport` (+ `generated_by`), §9.6 grounding rules (incl. exemptions), §7.11 language rule, §16 claims discipline
- T2d: §7.13 tools, §3.2 Converse + `toolConfig`, §10.1/§10.3/§10.4 (`AQUA_BEDROCK_MODEL_ID` = model or inference-profile ID), 20-s budget (§7.14.1)

## 3. Outputs — contracts produced
- `AgentRunner(settings).diagnose(incident) -> AgentReport` for module 08
- `template_report(incident) -> AgentReport` (`generated_by="template"`, `grounding_check.passed=true`)
- `check_grounding(report, tool_results) -> GroundingCheck` (T1 tests it against the template; T2d uses it live)
- `api/agent/fixtures/incidents/*.json` (10 recorded incidents), `api/agent/prompts/system_v1.md` (T2d)

## 4. Files owned
`api/agent/` (`template_reporter.py`, `grounding.py`, `tools.py`, `loop.py`, `smoke_bedrock.py`, `prompts/`, `fixtures/`), `api/clients/agent_runner.py`, `api/tests/test_agent_*.py`, `api/tests/test_grounding.py`.

## 5. Design decisions (binding)
- **T1 = TemplateReporter only.** Sentences are filled exclusively from `Incident` fields, formatted with `shared.units`. Example: "Pressure at S2 is {Δ} m below the model's expectation ({pct_change}%) while demand context is {context}." Every number comes from the incident, so grounding always passes. `headline` uses "probable leak" or "abnormal hydraulic behaviour" (no location until T2c; then "probable leak zone Zx / most likely pipe p"). `caveats` always include "Simulated network and synthetic sensor data". The UI shows the label "template explanation". *Rejected for T1:* any LLM call (latency, cost, IAM and grounding risk on the critical path).
- **Grounding checker (§9.6):** extract numbers with a regex (ints, decimals, signed, %). Normalise units (L/s↔L/min, m³/s↔L/s). Match ±0.5% or ±0.05 abs against all numeric leaves of the tool results. Exempt IDs, `HH:MM` labels present in the results, and ranks 1–5.
- **T2d Bedrock:** Converse with `toolConfig`; tools `get_incident`, `get_sensor_history`, `get_reconstruction`, `get_network_element` (+ `get_candidate_locations` once T2c exists), all with JSON Schemas generated from `shared.contracts` input models, plus `submit_report` (`SubmitReportInput`). Max 6 turns, temperature ≤ 0.2, **20-s wall-clock budget**, adaptive retries, one grounding retry, then the template. Model ID from env only (may be an inference profile). *Rejected:* Bedrock Agents/AgentCore (pitch "next step").
- *T3:* `run_what_if` (fork via 01), `/agent/ask`.

## 6. Implementation plan
| # | Step (≤ 2 h) | Done when |
|---|---|---|
| 1 | `template_reporter.py` + `AgentRunner` with `AQUA_AGENT=template`. Build 5 synthetic incidents from `shared/contracts/generated/examples.json`. | 5/5 reports validate as `AgentReport`, `generated_by="template"`. |
| 2 | `grounding.py` + tests (match, ±0.5%, ±0.05, unit conversion, ID/clock/rank exemptions, invented number fails). Templates pass. | `pytest api/tests/test_grounding.py` green. |
| 3 | Record 10 real incidents from 08's local pipeline into `fixtures/incidents/` (as soon as 08 step 4 works). | **G7 (T1):** 10 fixtures → 10 template reports, all grounded. |
| 4 | **T2d only:** `14_bedrock_check.sh` (D1/D2; MANUAL STEP if model access is missing), `tools.py`, `loop.py`, `smoke_bedrock.py`, `prompts/system_v1.md`. | `python -m api.agent.smoke_bedrock` returns a valid report for 1 fixture. |
| 5 | **T2d:** `AgentRunner` `bedrock` mode with grounding retry + fallback; mocked tests (success / invented number twice / throttling). | Mocked tests green; live: 10 fixtures → 10 reports `passed=true` (G7 T2d). |

## 7. AWS steps
T1: none. T2d:
```bash
bash infra/scripts/14_bedrock_check.sh                                # list Anthropic models + inference profiles
AQUA_BEDROCK_MODEL_ID=<id> bash infra/scripts/14_bedrock_check.sh     # "model replied: OK"; saves id + IAM ARNs
bash infra/scripts/03_iam_roles.sh && bash infra/scripts/11_ssm_params.sh && bash infra/scripts/09_ecs_service.sh
```
MANUAL STEP: Bedrock console → Model access, only if the Converse call reports missing access.

## 8. Tests
- **Unit:** template wording uses only incident values; grounding extractor/normaliser; (T2d) loop sequencing with a mocked client, max-turn and budget cut-offs.
- **Contract conformance:** reports → `AgentReport`; (T2d) tool outputs → their §7 models, `submit_report` → `SubmitReportInput`.
- **Firewall:** template/tool outputs never contain `LK_`, `hidden`, `truth`, or the challenge leak area (covered end-to-end by 08's firewall test).

## 9. Acceptance gate — G7
- [x] (T1) 7 recorded incidents (bursts/leaks on 7 pipes) → 7 reports — orig. target 10 → 10 template reports, schema-valid, `grounding_check.passed=true`, labelled template
- [x] (T2d) the same 10 → 10 Bedrock reports with `passed=true`; template fallback works with Bedrock disabled
- [x] (module) no hard-coded model ID (grep)

## 10. Risks and fallbacks
- T2d model access / inference profile issues: script 14; template stays the shipped explanation.
- 30-s API Gateway limit: 20-s budget → template.
- **Cut line:** if Bedrock is not grounded reliably by Day 4 midday, ship the template only (it is T1 anyway).

## 11. Handoff
- To **08**: `AgentRunner.diagnose`, `AQUA_AGENT`.
- To **09**: `generated_by` + `grounding_check` for the label and badge.
- To **10**: sample report text generated from a real incident (README / slides), never hand-written.

## 12. Agent prompt
```
You are implementing module 07 (explanation layer) of AquaAgent: T1 = TemplateReporter, T2d = Bedrock.
Read, in order and completely: INSTRUCTIONS.md, BACKBONE.md, docs/modules/07_AQUAAGENT_BEDROCK.md,
TILL_NOW.md (and docs/aws/02_BEDROCK_PRIMER.md only for T2d). Read nothing else.
Implement §6 steps 1–3 in order (steps 4–5 only when TILL_NOW shows gate MVP passed and T2a–T2c done);
after each run its "done when" check plus `make lint && make contracts-test &&
.venv/bin/python -m pytest api/tests -m "not bedrock"`, update TILL_NOW.md, STOP. Only edit files in §4.
Every number in a report must come from the Incident/tool results. Never hard-code a model id.
If a contract is wrong, write it under §13 and stop. Do not create git branches or push.
```

## 13. Proposed Backbone Changes
_(none blocking)_ Implementation notes (2026-10-10):
- `AgentRunner(settings).diagnose(ctx: IncidentContext)` — the context carries the Incident plus the SensorWindow and
  predictor response frozen at alarm time (tools need them; still firewall-safe).
- Model: Amazon Nova Lite (`apac.amazon.nova-lite-v1:0`) — cheapest model that grounded 7/7 in one call; Anthropic
  models currently blocked by `INVALID_PAYMENT_INSTRUMENT` (Marketplace). Switch with SSM `AQUA_BEDROCK_MODEL_ID`
  + `14_bedrock_check.sh` + `03_iam_roles.sh` + `09_ecs_service.sh`.
- Grounding pool also contains observed−baseline differences, unit conversions (relative tolerance only) and HH:MM
  labels of `*_time_s` fields; the first user turn carries the Incident + `labels` (clock labels, confidence policy).
- `confidence` is set by the orchestrator policy (`confidence_of`), not by the model.
- Extra routes: `GET /api/agent/info`; `POST /api/agent/diagnose` accepts `{incident_id?, refresh?}` and adds `run`
  (model, latency, tokens) to the AgentReport JSON.
