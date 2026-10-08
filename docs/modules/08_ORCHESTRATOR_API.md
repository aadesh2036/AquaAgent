# 08_ORCHESTRATOR_API.md
Backbone version: backbone/1.1.0 | Gate: **G8** (+ owns gate **MVP**) | Tier: **T1** | Est. effort: 10 h
Depends on: 01 (sim API), 04 (`predict`), 05 (detector), 07 (TemplateReporter) | Blocks: 09 (real API), 10, 03 (T2a deploy) | Schedule slot: Day 1 PM (skeleton: session, network, step, controls) · Day 3 AM (pipeline, challenge, reveal) (BACKBONE §13)

## 1. Purpose
The single public backend, `aquaagent-api`. It owns the interactive session (event log, challenge), drives the sim engine over HTTP, and builds `SensorWindow`s at the firewall. It runs predictor → detector → `Incident` → TemplateReporter, scores the reveal, and serves the frontend a truth-stripped `NetworkView`. T1 runs entirely locally with the predictor **in-process**. The same image later runs on ECS (T2a) and can switch to SageMaker (T2b) and Bedrock (T2d) through env vars only.

## 2. Inputs — contracts consumed
- §7.14.2 sim API + §7.4 `HydraulicSnapshot` + §7.3 `SimEvent` (01)
- §7.8 `SensorWindow`, §7.9 response (04 `predict`), §7.10 (05 detector), §7.12 `Incident` (`localisation` null until T2c), §7.13 `AgentReport` (07 TemplateReporter)
- §7.1 static config, §6.4 layout, §5.1–5.3 (IDs, units, single 300-s cadence), §8.3 noise, §10.4 env, §3.3 local/aws switch, §11 firewall
- `config/generation/ds1.yaml` leak ranges for challenge difficulty

## 3. Outputs — contracts produced
- Public API §7.14.1: every endpoint, `X-Aqua-Contract: backbone/1.1.0` on every response
- `aquaagent-api` image (`api/Dockerfile`)
- `data/demo/reveal_logs/<challenge_id>.json` for every challenge (G10 evidence)
- `api/scripts/e2e_challenge.py` (gate MVP / G8 / G10 runner)

## 4. Files owned
`api/app/` (`main.py`, `settings.py`), `api/routes/`, `api/session/` (`store.py`, `event_log.py`, `challenge.py`, `visibility.py`), `api/clients/` (`sim_client.py`, `predictor_client.py`; `agent_runner.py` is 07's), `api/pipeline/` (`window_buffer.py`, `incident.py`), `api/scripts/e2e_challenge.py`, `api/tests/` (except agent tests), `api/Dockerfile`, `api/requirements.txt`, `api/README.md`, `docker-compose.yml` (co-owned with 03).

## 5. Design decisions (binding)
- **FastAPI** under `/api`. Middleware adds `X-Aqua-Contract`. `X-Api-Key` is enforced only when `AQUA_MODE=aws` (`OPTIONS` exempt). FastAPI owns CORS (`AQUA_CORS_ORIGINS`).
- **One in-memory session per process** (`desiredCount=1` later). No background clock: time advances only on `POST /sim/step {steps}` (1/5/20 steps of 300 s).
- **Visibility filter is the only snapshot → `NetworkView` path:** unit conversion via `shared.units`, `hidden`/`LK_*`/hidden events dropped, `visual_fault=NONE` for the hidden challenge fault (physics still shows it), node status `ok/low/critical` from fixed pressure bands (document: low < 20 m, critical < 10 m).
- **Firewall boundary = `SensorWindowBuffer.push(snapshot)`:** copies S1–S3 pressures (m), F1–F2 flows (L/s) and context only, adds §8.3 noise (seeded per session), and keeps the last 12 steps. There is no subsampling, because everything is 300 s (§5.3). `PredictorClient.predict(window: SensorWindow)` is the only way into ML.
- **Pipeline per sim step:** once the buffer has ≥ 4 steps (lag3 available) → `predict` → `residual_frame` → `RTCADetector.update` → `network_status`. On the first ANOMALY: `build_incident` (evidence = LOO predicted vs observed per driving sensor with `pct_change`, context summary; `localisation=None` until T2c) → stored by `ids.incident_id`.
- **`AQUA_MODE`:** `local` (T1) loads the model artifact from `AQUA_PREDICTOR_ARTIFACT` (default `data/models/predictor/<version>/`) in-process and thresholds from a local path. `aws` (T2) can read the same artifact from S3 (T2a) or call SageMaker (T2b, `AQUA_PREDICTOR_ENDPOINT` set). `AQUA_AGENT=template` (T1) | `bedrock` (T2d).
- **Challenge:** `start` draws (seeded) a location from the 14 candidates minus sensor junctions 2/4/6 and an area from the difficulty's leak range (default medium). It applies a hidden `PIPE_FAULT` starting 1–3 steps later and resets the detector. `status`: `RUNNING` → `DETECTED` (incident created) → or `TIMEOUT` after 36 steps (3 h sim) without detection. `reveal`: truth from the challenge record; AI = detected, `detection_delay_s` (true start → confirmed), and rank/zone `null` until T2c. Writes the reveal log.
- `/agent/diagnose` → `AgentRunner` (07): template, instant, in T1.

## 6. Implementation plan
| # | Step (≤ 2 h) | Done when |
|---|---|---|
| 1 | `make setup-api`. `create_app()`, settings, contract header, CORS, key middleware, `/api/health`; `SimClient` (httpx, §7.14.2 models); `/session/reset`, `/network/topology`, `/network/state`, `/sim/step`; `visibility.py`. | With 01's server running: reset → step 5 → `NetworkView` validates; demand_lps = `m3s_to_lps(demand_m3s)` (test); header present. |
| 2 | `/tap`, `/pipe/fault`, `/valve` → `SimEvent`s + event text. | Opening T2 raises node-4 demand in the next view; the event appears in `events`. (This finishes Day-1's first vertical slice together with 09.) |
| 3 | `SensorWindowBuffer` (noise, null missing, ≤ 12 steps) + in-process `PredictorClient` (04 `predict`). | Buffer yields a valid `SensorWindow`; `predict` returns a valid `PredictorResponse` from the local artifact. |
| 4 | Pipeline: residual → detector → `network_status` → `Incident`. | A user-made LARGE leak drives `network_status` to ANOMALY within ≤ 12 steps; `Incident` validates and contains no truth. |
| 5 | Challenge start/status/reveal + reveal logs; `/agent/diagnose` via 07 template. | Local loop: start → DETECTED → diagnose → reveal → valid `ChallengeReveal`; reveal log written. |
| 6 | **Firewall test** + schema conformance for every endpoint. | `pytest api/tests/test_firewall.py api/tests/test_schema_conformance.py` green. |
| 7 | `api/scripts/e2e_challenge.py --base URL --runs N`; `docker compose up` (sim + api + frontend). | **Gate MVP:** clean checkout → `make compose-up` → `e2e_challenge --base http://localhost:8080 --runs 3` → 3/3 detected, reveals valid. |
| 8 | (T2a) `AQUA_MODE=aws` artifact from S3; deploy via 03 scripts. (T2b) SageMaker client. | G8 on AWS: e2e against the API Gateway URL. |

## 7. AWS steps
T1: none (`docker compose`). T2a/T2b: see `docs/modules/03_AWS_INFRA.md` and `06_SAGEMAKER.md`. The image and code are unchanged, only env differs:
```bash
make images && bash infra/scripts/11_ssm_params.sh && bash infra/scripts/09_ecs_service.sh
python -m api.scripts.e2e_challenge --base "$(cat infra/.state/api_url)" --api-key "$KEY" --runs 3
```

## 8. Tests
- **Unit:** visibility conversions (units, clock, level_pct, direction sign, status bands); event-log hidden filtering; buffer noise/null/length; challenge scoring (delay) on synthetic records; key middleware (aws mode: 401 without key, OPTIONS passes).
- **Contract conformance (`test_schema_conformance.py`):** every §7.14.1 response validates; `X-Aqua-Contract == CONTRACT_VERSION` everywhere.
- **Firewall (BACKBONE §11, G8) — `api/tests/test_firewall.py`:** start a challenge with a known hidden leak (location P, `LK_P`, area A). Call **every** public endpoint (`/health`, `/session/reset`, `/network/topology`, `/network/state`, `/sim/step`, `/tap`, `/pipe/fault`, `/valve`, `/challenge/start`, `/challenge/status`, `/agent/diagnose`) and, from T2d, every agent tool. Serialise all of it and assert none contains `LK_`, the value A (any formatting), `"hidden"`, `"truth"`, a non-`NONE` `visual_fault` on P, or a challenge event, before `/challenge/reveal`. After reveal, the truth is present.
- **Type firewall:** `PredictorClient.predict` rejects a `HydraulicSnapshot`.

## 9. Acceptance gate — G8 (+ MVP)
- [ ] all §7.14.1 endpoints conform to schema
- [ ] firewall test (§11) passes
- [ ] full challenge loop runs end-to-end locally
- [ ] **MVP:** `docker compose up` on a clean checkout → 3 consecutive clean challenge runs
- [ ] (T2a) the same loop on AWS

## 10. Risks and fallbacks
- 20× too slow: measure `/sim/step {20}` latency (expected ≈ 0.4 s from 18 ms/step); cap UI speed at 5× if needed.
- No detection within the timeout for small leaks: the demo uses `medium`; the reveal shows "not detected" honestly.
- Detector state after the user's own leaks: `/session/reset` and `/challenge/start` reset the detector and buffer.

## 11. Handoff
- To **09**: base URL; §7.14.1 shapes; tick = `POST /sim/step {steps: speed}` every 1 s; poll `/challenge/status` every 1 s while RUNNING.
- To **07**: `Incident` store + window buffer for template wording (T2d: tool context).
- To **10**: `e2e_challenge.py`, reveal logs, `/health` for warm-up.
- To **03 (T2a)**: image, env (`AQUA_MODE`, `AQUA_PREDICTOR_ARTIFACT`/S3 URI, thresholds URI, CORS, API key), health path.

## 12. Agent prompt
```
You are implementing module 08 (Orchestrator API) of AquaAgent.
Read, in order and completely: INSTRUCTIONS.md, BACKBONE.md, docs/modules/08_ORCHESTRATOR_API.md,
TILL_NOW.md. Read nothing else; use modules 01/04/05/07 only through the interfaces in §2/§11.
Implement §6 in order (step 8 only after gate MVP); after each run its "done when" check plus
`make lint && make contracts-test && .venv/bin/python -m pytest api/tests`, update TILL_NOW.md, STOP.
Only edit files in §4. Every response carries X-Aqua-Contract; only SensorWindow reaches ML; the visibility
filter is the only snapshot→NetworkView path; hidden events never leave before reveal. The firewall test is
mandatory. If a contract is wrong, write it under §13 and stop. Do not create git branches or push.
```

## 13. Proposed Backbone Changes
_(empty)_
