# RUNBOOK.md — clone → working MVP (local) → AWS (T2) → teardown

> `backbone/1.1.0`. **Part A is the plan; Part B is the bonus.** Do not start Part B before gate **MVP** passes (BACKBONE §12).
> Each step gives the command, the gate it serves, the expected result, and what to do if it fails. ✂ = cut line (BACKBONE §13). 🖐 = MANUAL STEP.
> Steps marked "after module NN" only work once that module is implemented. Until then the target exits 2 with `NOT IMPLEMENTED — see docs/modules/NN`.
> Agents: read [INSTRUCTIONS.md](../INSTRUCTIONS.md) first. Progress lives in [TILL_NOW.md](../TILL_NOW.md).

---

## Part A — T1 MVP detection loop (local, no AWS)

### A1. Setup (now)
```bash
make setup             # Python 3.12 .venv via uv (+ wntr==1.5.0), .env + infra/env.sh templates
make lint && make contracts-test
make feasibility       # reproduces docs/research/WNTR_FEASIBILITY.md numbers
```
- **Expected:** `python 3.12.x wntr 1.5.0`; `lint OK`; pytest 36 passed; node pass 7; spike prints `stop/restart vs full run max|dP| … 0.00e+00`.
- **If it fails:** no `uv` → install it (`pip install --user uv`) or have `python3.12` on PATH. WNTR has no wheels for Python 3.14 (BI-22).

### A2. Simulation engine (module 01) — G1
```bash
make sim-smoke
make sim-serve &   curl -s localhost:8000/sim/health
```
- **Expected:** 289 snapshots, mass balance ≤ 1e-4, leaks change pressures; `{"status":"ok","wntr_version":"1.5.0"}`.
- ✂ **End of Day 1:** pre-split pipe leaks misbehave → junction leaks only.

### A3. First vertical slice (modules 08 steps 1–2 + 09 steps 1–3)
```bash
make setup-api && make api-serve &        # :8080
cd frontend && npm install && VITE_MOCK_API=false npm run dev    # :5173
```
- **Expected:** a live network animates. Opening tap T2 changes node 4 on the next tick (handoff §39 slice: React → FastAPI → WNTR → SVG).

### A4. Dataset (module 02) — G2
```bash
make datagen-local N=20 && .venv/bin/python -m pytest sim/tests/test_generate_repro.py
.venv/bin/python -m sim.generate.calibrate        # writes final leak ranges into config/generation/ds1.yaml
make datagen-ds1 SHARDS=8                         # 1,200 sims → data/processed/ds1/ + manifest.json
```
- **Expected:** identical hashes; `calibration.done: true`; manifest `n_valid ≥ 1140`. This takes minutes (≈0.2 s per sim).

### A5. Predictor (module 04) — G4
```bash
make setup-ml && make features && make train-local
.venv/bin/python -m pytest ml/tests/test_leakage.py
```
- **Expected:** the MLP beats the baseline on hidden-node MAE; hop table under `data/experiments/<mv>/`.
- ✂ **End of Day 2:** if the MLP does not beat the baseline → ship the baseline (D4).

### A6. Detector (module 05 steps 1–5) — G5 (T1 rows)
```bash
make tune     # val only → data/models/anomaly/thr_ds1_*/thresholds.json — record its SHA-256 in TILL_NOW BEFORE test
```
- **Expected:** FAR ≤ 5% per operational type on val; the test detection table is written once.

### A7. Orchestrator + explanation (module 08 steps 3–7, module 07 steps 1–3) — G7 (T1), G8
```bash
.venv/bin/python -m pytest api/tests/test_firewall.py api/tests/test_schema_conformance.py
```

### A8. Gate MVP
```bash
make compose-up          # clean checkout: sim :8000, api :8080, frontend :5173
make mvp                 # 3 challenge runs: start → DETECTED → report → reveal
```
- **Expected:** 3/3 detected, reveal logs in `data/demo/reveal_logs/`. Record in TILL_NOW. **Only now does Part B begin.**
- ✂ **Evening Day 3:** MVP not clean → no T2; Day 4 AM fixes the MVP.

### A9. Demo assets (module 10) — G10
Record the fallback video of the working stack; build slides only from `data/experiments/` numbers.

---

## Part B — T2 (in order, each only if the previous is green)

### Values to confirm before running Part B
Every `<VERIFY: …>` placeholder in the repo:

| # | Placeholder | Where | How to confirm | Needed by |
|---|---|---|---|---|
| V1 | `AQUA_SM_TRAIN_INSTANCE` | `infra/env.sh` | CPU `ml.*` type with quota ≥ 1: `aws service-quotas list-service-quotas --service-code sagemaker --query "Quotas[?contains(QuotaName,'<type> for training job usage')].Value"` | B4 |
| V2 | `AQUA_SM_INFER_INSTANCE` | `infra/env.sh` | the same with `'for endpoint usage'`; p95 < 300 ms via `ml.sagemaker.smoke_invoke` | B4 |
| V3 | `AQUA_SM_PT_VERSION` (and the torch pin in `ml/requirements.txt`) | `infra/env.sh` | `image_uris.retrieve('pytorch', region, version=…, py_version=…, instance_type=…, image_scope='training')` prints a URI | B4 |
| V4 | `AQUA_SM_PY_VERSION` | `infra/env.sh` | same as V3 | B4 |
| V5 | SageMaker SDK version/API + the helper that lists framework versions | `ml/requirements.txt`, `docs/aws/01_SAGEMAKER_PRIMER.md` | `python -c "import sagemaker; print(sagemaker.__version__)"` + SDK docs | B4 |
| V6 | `AQUA_BEDROCK_MODEL_ID` (model **or inference-profile** ID) | `infra/env.sh` | `bash infra/scripts/14_bedrock_check.sh` until "model replied: OK" | B6 |
| V7 | `toolChoice` support for the chosen model | `docs/aws/02_BEDROCK_PRIMER.md` | module 07 step 4: a forced `submit_report` call; `ValidationException` → prompt-only path | B6 |
| V8 | `CODEBUILD_IMAGE` | `infra/env.sh` | `aws codebuild list-curated-environment-images` (only with the no-docker fallback) | B2 |
| V9 | `APIGW_THROTTLE_BURST/RATE` | `infra/env.sh` | small values (1 viewer ≈ 2 req/s); load-test with `e2e_challenge` | B2 |
| — | ~~HTTP API timeout~~ | resolved: 30 s, not adjustable (WNTR_FEASIBILITY §4) | — | — |
| — | ~~WNTR pin~~ | resolved: `wntr==1.5.0` (re-confirm in G1) | — | — |

### B1. AWS prerequisites (optional on Day 1: 5 minutes)
```bash
$EDITOR infra/env.sh                 # AWS_PROFILE (laptop), AWS_REGION, BUDGET_EMAIL
make aws-prereqs                     # PASS/FAIL table
bash infra/scripts/01_budget_alert.sh
```

### B2. T2a — deploy the working T1 stack (module 03) — G3, G8 (AWS), G9 (Amplify)
```bash
make aws-bootstrap                                       # budget, S3, IAM, ECR
make images                                              # docker or CodeBuild fallback
bash infra/scripts/06_ecs_cluster.sh
aws s3 sync data/processed/ds1 s3://$AQUA_BUCKET/processed/ds1/
aws s3 sync data/models s3://$AQUA_BUCKET/models/
bash infra/scripts/08_network_alb.sh
AQUA_AGENT=template bash infra/scripts/11_ssm_params.sh   # BEFORE 09 (task secrets come from SSM)
bash infra/scripts/09_ecs_service.sh
bash infra/scripts/10_apigw_https.sh                     # prints the HTTPS base URL (G3: curl …/api/health)
make deploy-frontend                                     # 🖐 MANUAL STEP: Amplify ↔ GitHub OAuth
bash infra/scripts/11_ssm_params.sh && bash infra/scripts/09_ecs_service.sh   # CORS for the Amplify origin
KEY=$(aws ssm get-parameter --name /aquaagent/AQUA_API_KEY --with-decryption --query Parameter.Value --output text)
.venv/bin/python -m api.scripts.e2e_challenge --base "$(cat infra/.state/api_url)" --api-key "$KEY" --runs 3
```
- **If it fails:** `aws logs tail /ecs/aquaagent-api --since 15m`; targets unhealthy → `/api/health` must answer 200; CORS errors → re-run 11 + 09.

### B3. (re-entry) publish new model/threshold versions
```bash
AQUA_PREDICTOR_VERSION=<mv> AQUA_THRESHOLDS_URI=s3://… bash infra/scripts/11_ssm_params.sh && bash infra/scripts/09_ecs_service.sh
```

### B4. T2b — SageMaker (module 06) — G6
```bash
python3 -m ml.sagemaker.launch_training --local   # laptop + docker first
make sm-train && make sm-deploy MV=<model_version>
python3 -m ml.sagemaker.smoke_invoke --endpoint-name aquaagent-predictor --n 50 --parity-artifact data/models/predictor/<mv>/model.tar.gz
```
- If the endpoint misbehaves, keep the in-process predictor. Nothing in the demo depends on the endpoint.

### B5. T2c — localisation (module 05 steps 6–7)
Signatures → matcher → localisation metrics; the reveal shows the rank of the true pipe.

### B6. T2d — Bedrock agent (module 07 steps 4–5) — G7 (T2d)
```bash
bash infra/scripts/14_bedrock_check.sh                               # 🖐 model access if needed
AQUA_BEDROCK_MODEL_ID=<id> bash infra/scripts/14_bedrock_check.sh
bash infra/scripts/03_iam_roles.sh && AQUA_AGENT=bedrock bash infra/scripts/11_ssm_params.sh && bash infra/scripts/09_ecs_service.sh
```
- ✂ **Day 4 midday:** stop starting new T2 items.

---

## Part C — Demo day + teardown

### C1. Demo-day checklist (module 10)
- [ ] `make status` (T2) or `make compose-up` (T1) healthy; `/api/health` ok
- [ ] (T2b) warm endpoint call
- [ ] fallback video saved (`s3://…/demo/` or local)
- [ ] every slide number traced to `experiments/`
- [ ] feature freeze 3 h before judging; phone hotspot ready

### C2. Teardown (only if Part B was used)
```bash
bash infra/scripts/99_teardown.sh --endpoint-only     # right after judging
make teardown                                         # keeps S3 evidence
make teardown ARGS=--purge                            # final, irreversible
```
