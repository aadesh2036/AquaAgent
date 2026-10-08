# 06_SAGEMAKER.md
Backbone version: backbone/1.1.0 | Gate: **G6** | Tier: **T2b** | Est. effort: 6 h
Depends on: gate MVP, 03 (T2a), 04 | Blocks: 08 `AQUA_MODE=aws` predictor (optional) | Schedule slot: Day 4 AM, only after T2a (BACKBONE §13)

> **New to SageMaker? Read [docs/aws/01_SAGEMAKER_PRIMER.md](../aws/01_SAGEMAKER_PRIMER.md) first.** It explains Training Job vs Model vs Endpoint Config vs Endpoint, script mode, `model.tar.gz`, the execution role and local mode, all of which this module relies on.

## 1. Purpose
Run module 04's unchanged `train.py` as a reproducible SageMaker Training Job from S3 inputs, then serve the resulting `model.tar.gz` on a real-time endpoint. The endpoint implements the §7.9 contract (reconstruct + leave-one-out in one call) with p95 < 300 ms, and must give identical outputs (±1e-5) to the local `AQUA_MODE=local` path.

## 2. Inputs — contracts consumed
- §7.8 `SensorWindow`, §7.9 `PredictorRequest`/`PredictorResponse` (incl. `leave_one_out_flow`)
- §3.2 (PyTorch framework container, script mode, CPU, real-time 1 instance), §10.2 (`features/`, `models/predictor/`), §10.3 (`aqua-sagemaker-exec`), §10.4 (`AQUA_PREDICTOR_ENDPOINT`, `AQUA_PREDICTOR_VERSION`), §10.5 (delete after judging)
- Module 04: `ml/predictor/train.py`, `ml/predictor/predict.py`, artifact layout, `features/ds1/`
- Module 03: `infra/.state/sagemaker_role_arn`, scripts 12/13
- §7.7/§10.5: inference reads scalers from inside model.tar.gz
- **Precondition:** gate MVP passed and T2a (S3, ECS) done. T1 already serves the same `predict()` in-process; this module only moves it behind an endpoint.

## 3. Outputs — contracts produced
- SageMaker training job `aquaagent-<arch>-<ts>` → `s3://…/models/predictor/<model_version>/model.tar.gz`
- Real-time endpoint `aquaagent-predictor` serving §7.9
- `experiments/<model_version>/sagemaker.json`: job name, image URI (as retrieved), instance types, p50/p95 latency, parity max|Δ|

## 4. Files owned
`ml/sagemaker/` (`launch_training.py`, `deploy_endpoint.py`, `inference.py`, `smoke_invoke.py`), `ml/tests/test_inference_handlers.py`, `ml/tests/test_parity.py`. (`infra/scripts/12_*.sh`, `13_*.sh` are wrappers owned by 03. Fix them together with 03.)

## 5. Design decisions (binding)
- **Script mode, PyTorch framework container, CPU instance** (§3.2: CPU is sufficient for an 8-node graph). The image URI comes from `sagemaker.image_uris.retrieve(...)` using `AQUA_SM_PT_VERSION`/`AQUA_SM_PY_VERSION` (`<VERIFY>`). **Never hard-code an image URI.** *Rejected:* a custom training container (extra build, no benefit).
- **Same `train.py`** as local (04). Channels: `train`, `val` → `s3://…/features/ds1/`. Hyper-params passed as CLI args. `output_path = s3://…/models/predictor/`, and the job then copies to `models/predictor/<model_version>/model.tar.gz`.
- **`inference.py` placed at `code/inference.py` inside model.tar.gz**, importing `ml.predictor.predict` (vendored into `code/` at package time, along with `shared/contracts` + `shared/units`). `input_fn` validates `PredictorRequest`. `predict_fn` returns **both** `reconstruct` and `leave_one_out` regardless of `mode`, plus `latency_ms` (§7.9: one call, not four). `output_fn` → JSON.
- **Real-time endpoint, 1 instance, smallest type that passes p95 < 300 ms** (`AQUA_SM_INFER_INSTANCE`, `<VERIFY>`). *Rejected:* serverless (cold start vs G6/§14).
- **Local mode first** (`--local`, Docker on a laptop) before paying for instances.
- **Parity**: the same `model.tar.gz` loaded in-process (local client) vs the endpoint, on 50 recorded windows → max|Δ| ≤ 1e-5 (G6).

## 6. Implementation plan
| # | Step (≤ 2 h) | Done when |
|---|---|---|
| 1 | Confirm `<VERIFY>` values: SDK version, supported PyTorch/py versions (`image_uris`), CPU instance types + **quotas** for training and endpoint. Fill `infra/env.sh`. | `python -c "from sagemaker import image_uris; print(image_uris.retrieve('pytorch', '$AWS_REGION', version='$AQUA_SM_PT_VERSION', py_version='$AQUA_SM_PY_VERSION', instance_type='$AQUA_SM_TRAIN_INSTANCE', image_scope='training'))"` prints a URI; quota ≥ 1 for both instance types. |
| 2 | `inference.py` four handlers + packaging helper that builds `model.tar.gz` (model.pt, scalers.json, meta.json, `code/inference.py`, vendored `code/` deps). | `pytest ml/tests/test_inference_handlers.py`: handlers called in-process on the §7.9 example return a valid `PredictorResponse`. |
| 3 | `launch_training.py` (PyTorch Estimator, role from state, channels, hyper-params, tags `project=aquaagent`, `--local`). | `python -m ml.sagemaker.launch_training --local` completes and produces a model.tar.gz (laptop with Docker). |
| 4 | Real job: `make sm-train`. Copy the artifact to `models/predictor/<model_version>/`. | `aws sagemaker describe-training-job … --query TrainingJobStatus` = `Completed`; artifact in S3. Re-running with the same inputs/seed gives the same val metrics (reproducible from S3 inputs). |
| 5 | `deploy_endpoint.py` (Model with `image_scope="inference"` URI, EndpointConfig, Endpoint; update-in-place if it exists). | `make sm-deploy MV=<mv>` → InService; script 13's smoke invoke prints a §7.9-valid body. |
| 6 | `smoke_invoke.py`: N=50 calls → p50/p95; parity vs local artifact. | p95 < 300 ms and max|Δ| ≤ 1e-5, written to `experiments/<mv>/sagemaker.json`. |
| 7 | Publish `AQUA_PREDICTOR_VERSION` to SSM (`11_ssm_params.sh`); document warm-up + delete in TILL_NOW. | `aws ssm get-parameter --name /aquaagent/AQUA_PREDICTOR_VERSION` = `<mv>`. |

## 7. AWS steps
```bash
# confirm values (RUNBOOK "Values to confirm"): AQUA_SM_TRAIN_INSTANCE, AQUA_SM_INFER_INSTANCE, AQUA_SM_PT_VERSION, AQUA_SM_PY_VERSION
aws service-quotas list-service-quotas --service-code sagemaker \
  --query "Quotas[?contains(QuotaName,'$AQUA_SM_TRAIN_INSTANCE') || contains(QuotaName,'$AQUA_SM_INFER_INSTANCE')].[QuotaName,Value]" --output table
make sm-train                                     # infra/scripts/12_sagemaker_train.sh
aws logs tail /aws/sagemaker/TrainingJobs --since 30m --follow
make sm-deploy MV=<model_version>                 # infra/scripts/13_sagemaker_deploy.sh (+ smoke invoke)
python3 -m ml.sagemaker.smoke_invoke --endpoint-name aquaagent-predictor --n 50 --parity-artifact data/models/predictor/<mv>/model.tar.gz
AQUA_PREDICTOR_VERSION=<mv> infra/scripts/11_ssm_params.sh && infra/scripts/09_ecs_service.sh
# AFTER JUDGING — stops the hourly bill:
infra/scripts/99_teardown.sh --endpoint-only      # = aws sagemaker delete-endpoint --endpoint-name aquaagent-predictor
```

## 8. Tests
- **Unit:** handlers (`model_fn` loads scalers from inside the tarball, `input_fn` rejects a non-`SensorWindow` payload; `output_fn` JSON); packaging layout check (tar listing).
- **Contract conformance:** endpoint response validates as `PredictorResponse` (script 13 does this) and contains both `reconstruct` and `leave_one_out`.
- **Parity (G6):** `ml/tests/test_parity.py` (local handlers vs in-process predictor ±1e-5), and `smoke_invoke --parity-artifact` (endpoint vs local).
- **Firewall:** `input_fn` accepts only `PredictorRequest` → `SensorWindow`. A test sends extra fields (`hidden`, `leak_m3s`) and expects rejection (`extra="forbid"`).

## 9. Acceptance gate — G6
Copied from BACKBONE §12, plus module checks:
- [ ] training job reproducible from S3 inputs
- [ ] endpoint returns §7.9 schema
- [ ] p95 latency < 300 ms
- [ ] `AQUA_MODE=local` produces identical outputs (±1e-5) from the same artifact
- [ ] (module) no hard-coded image URI / instance type (grep)
- [ ] (module) endpoint deletion command documented and tested once (`--endpoint-only`)

## 10. Risks and fallbacks
- Quota 0 for the chosen instance: check on step 1, pick another type, request an increase on Day 1.
- Framework/py version mismatch: `image_uris.retrieve` from step 1 only.
- Endpoint cold start / latency (§14): real-time instance; warm with a call before the demo (module 10).
- **Fallback:** if the endpoint is not serving, nothing breaks: the api keeps the in-process predictor (T1 default) and the training job alone is the SageMaker story. Record it in TILL_NOW and tell 08/10.

## 11. Handoff
- To **08**: endpoint name (`AQUA_PREDICTOR_ENDPOINT`), model version (SSM), request/response = §7.9, and the same `model.tar.gz` for the local fallback.
- To **03**: endpoint lifecycle for `99_teardown.sh`; IAM needs (`sagemaker:InvokeEndpoint` on the endpoint ARN, already templated).
- To **10**: `experiments/<mv>/sagemaker.json` (latency, parity) for slides; warm-up command.

## 12. Agent prompt
```
You are implementing module 06 (SageMaker) of AquaAgent. The human is new to SageMaker — explain each AWS
action in one sentence before running it.
Read, in order and completely: INSTRUCTIONS.md, BACKBONE.md, docs/modules/06_SAGEMAKER.md, TILL_NOW.md,
the module 06 rows in docs/BACKBONE_ISSUES.md, and docs/aws/01_SAGEMAKER_PRIMER.md. Nothing else for context.
Implement §6 in order; after each step run its "done when" check plus `make lint && make contracts-test`,
update TILL_NOW.md, STOP. Only edit files in §4. Use module 04's train.py and predict.py UNCHANGED.
Never hard-code image URIs, instance types or account IDs: discover via sagemaker.image_uris and read from
infra/env.sh (mark <VERIFY>). Confirm with the human before any step that creates billable resources.
Endpoint must return BOTH reconstruct and leave_one_out per §7.9. If a contract is wrong, write it under §13
and stop. Do not create git branches or push.
```

## 13. Proposed Backbone Changes
_(empty)_
