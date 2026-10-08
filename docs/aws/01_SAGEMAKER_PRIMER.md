# 01 — SageMaker Primer for AquaAgent

> Prereq: [00_AWS_PRIMER.md](00_AWS_PRIMER.md). Implementation lives in [docs/modules/06_SAGEMAKER.md](../modules/06_SAGEMAKER.md).
> BACKBONE refs: §3.2 (Training Job + real-time endpoint), §7.9 (endpoint contract), §9.1 (training rules), §10.2–10.5, G6.

## 1. Mental model in one diagram

```
           (you)  python ml/sagemaker/launch_training.py
                         │  "run train.py in the PyTorch container on <instance>"
                         ▼
 s3://…/features/ds1/ ──▶ TRAINING JOB ──(container exits)──▶ s3://…/models/predictor/<mv>/model.tar.gz
   mounted at              • starts an instance                 (whatever train.py wrote to SM_MODEL_DIR)
   /opt/ml/input/data/      • runs YOUR train.py (script mode)
   train|val                • logs → CloudWatch /aws/sagemaker/TrainingJobs
                            • you pay only while it runs

           (you)  python ml/sagemaker/deploy_endpoint.py
                         ▼
   MODEL  = model.tar.gz + inference container image + execution role
   ENDPOINT CONFIG = which MODEL, which instance type, how many
   ENDPOINT = a live HTTPS service built from the config   ◀── you pay EVERY HOUR it exists
                         ▲
   api container ── boto3 sagemaker-runtime.invoke_endpoint(JSON §7.9) ──┘
```

## 2. The concepts that matter here

1. **Training Job vs Model vs Endpoint Config vs Endpoint.** A *Training Job* is a batch run that produces `model.tar.gz` and then stops. A *Model* is a registration that pairs that tarball with a serving image and a role. An *Endpoint Config* says "model X on instance type Y × 1". An *Endpoint* is the running service. Deleting the endpoint stops the bill. The model and config are just metadata.
2. **Script mode with the PyTorch framework container.** AWS provides the PyTorch image, and you supply `train.py`. SageMaker passes data locations through env vars: `SM_CHANNEL_TRAIN`, `SM_CHANNEL_VAL`, `SM_MODEL_DIR`, `SM_OUTPUT_DATA_DIR`. Our `ml/predictor/train.py` reads these **with local defaults**, so the *same file* runs on your laptop (`make train-local`) and on SageMaker (§3.2: "same script local + SageMaker").
   ```python
   p.add_argument("--train", default=os.environ.get("SM_CHANNEL_TRAIN", "data/features/ds1"))
   p.add_argument("--model-dir", default=os.environ.get("SM_MODEL_DIR", "data/models/predictor/local"))
   ```
3. **`model.tar.gz` layout.** Whatever `train.py` writes to `SM_MODEL_DIR` gets tarred. For PyTorch serving we include the inference code:
   ```
   model.tar.gz
   ├── model.pt            # weights (state_dict)
   ├── scalers.json        # train-split scalers (BACKBONE_ISSUES BI-09: inference reads THIS copy)
   ├── meta.json           # model_version, feature order (NODE/EDGE_FEATURES_V1), sensor layout
   └── code/
       ├── inference.py    # model_fn, input_fn, predict_fn, output_fn
       └── requirements.txt (optional)
   ```
   The four handlers: `model_fn(model_dir)` loads once. `input_fn(body, content_type)` parses the JSON into a `PredictorRequest`. `predict_fn(req, model)` returns the dict for §7.9, with **both** `reconstruct` and `leave_one_out` in one call. `output_fn(pred, accept)` serialises it to JSON.
4. **Execution role** (`aqua-sagemaker-exec`, §10.3). SageMaker assumes this role to read `features/`, write `models/` and `experiments/`, pull the framework image, and write logs. If the role is missing a permission, the job fails at "Downloading data" or "Uploading".
5. **Image URIs are discovered, never typed.** Use `sagemaker.image_uris.retrieve("pytorch", region, version=…, py_version=…, instance_type=…, image_scope="training"|"inference")`. The version and py_version come from `infra/env.sh` (`AQUA_SM_PT_VERSION`, `AQUA_SM_PY_VERSION`, `<VERIFY>`).
6. **Real-time vs serverless endpoint.** A serverless endpoint scales to zero and is cheaper, but it has **cold starts** (seconds) on the first call after it goes idle. G6 needs p95 < 300 ms during a live demo, and §14 lists cold start as a risk, so BACKBONE chooses a **real-time** endpoint with 1 instance. We warm it before the demo and delete it after judging (§10.5).
7. **CloudWatch logs for a failed job.** `aws sagemaker describe-training-job --training-job-name <n> --query FailureReason` gives a one-line reason, and `aws logs tail /aws/sagemaker/TrainingJobs --log-stream-name-prefix <n> --since 1h` gives the full traceback. Endpoint logs are in `/aws/sagemaker/Endpoints/<endpoint-name>`.
8. **Local mode first.** `instance_type="local"` in the SDK runs the *same container* on your machine with Docker. This catches packaging and handler bugs for free. It needs Docker, so run it on a laptop, not in CloudShell.

## 3. How AquaAgent uses it

| Step | BACKBONE | File / script |
|---|---|---|
| Upload features | §10.2 `features/ds1/` | module 04 output → `aws s3 sync data/features/ds1 s3://$AQUA_BUCKET/features/ds1/` |
| Train (same script) | §9.1, G6 | `ml/predictor/train.py` via `ml/sagemaker/launch_training.py` (`make sm-train`) |
| Package | §7.9, BI-09 | `train.py` writes model.pt + scalers.json + meta.json + `code/inference.py` |
| Deploy | §3.2 | `ml/sagemaker/deploy_endpoint.py` (`make sm-deploy MV=<mv>`) |
| Invoke | §7.9 | `api/clients/predictor_client.py` (`AQUA_MODE=aws`) |
| Parity | G6 ±1e-5 | `ml/sagemaker/smoke_invoke.py --parity-artifact` |
| Cut line | §13 midday Day 3 | `AQUA_MODE=local`: the api loads the same `model.tar.gz` in-process |

## 4. Commands, in order (expected output shape)

```bash
# 0. Values to confirm (RUNBOOK): instance types + framework version.
python3 -c "import sagemaker; print(sagemaker.__version__)"
python3 - <<'PY'
from sagemaker import image_uris
# Lists versions the SDK knows (<VERIFY: helper name for your SDK version>). Pick one, then set AQUA_SM_PT_VERSION / AQUA_SM_PY_VERSION in infra/env.sh
print(image_uris.config_for_framework("pytorch")["training"]["versions"].keys())
PY

# 1. Local training (no AWS cost)
make train-local
# → data/models/predictor/local/{model.pt,scalers.json,meta.json,code/inference.py}

# 2. Local-mode SageMaker (Docker required; laptop only)
python3 -m ml.sagemaker.launch_training --local
# → "Training seconds: …" and a local model.tar.gz

# 3. Real training job
make sm-train
# → TrainingJobName: aquaagent-mlp-2026…  Status: Completed
aws sagemaker list-training-jobs --name-contains aquaagent --max-results 3 \
  --query 'TrainingJobSummaries[].[TrainingJobName,TrainingJobStatus]' --output table

# 4. Deploy + smoke
make sm-deploy MV=mlp_ds1_202610100930
# → EndpointStatus InService; prints a §7.9 JSON with reconstruct + leave_one_out
python3 -m ml.sagemaker.smoke_invoke --endpoint-name aquaagent-predictor --n 50
# → p50=…ms p95=…ms (must be < 300)   parity max|Δ|=…(must be ≤ 1e-5)

# 5. After judging (stops the hourly bill)
infra/scripts/99_teardown.sh --endpoint-only
```

## 5. The five most common errors

| Error | Cause | Fix |
|---|---|---|
| `AccessDeniedException … s3:GetObject` in the job log | **Permissions**: the execution role cannot read `features/`. | Check `aqua-sagemaker-exec` policy prefixes. Re-run `03_iam_roles.sh`. |
| `Could not find model data` / bucket in a different region | **Region** mismatch between bucket and job. | Everything must be in `$AWS_REGION` (§10.1). |
| `ResourceLimitExceeded … for training job usage` | **Quota** is 0 for that instance type. | Choose another CPU type, or request a quota increase on Day 1 (see 00 primer §5). |
| `ValueError: Unsupported pytorch version` / `image not found` | **Image URI**: version/py_version combination not supported. | Use `image_uris.retrieve` with a version from step 0. Never paste URIs. |
| Endpoint `Failed` / `ModelError` on invoke | `inference.py` crashed, or the tarball layout is wrong. | `aws logs tail /aws/sagemaker/Endpoints/aquaagent-predictor --since 30m`. Test with local mode first. |

(Model access is a Bedrock issue, not a SageMaker one. See the Bedrock primer.)

## 6. Cost notes and what to delete

- Training job: billed per second while running only. With CPU and a tiny network this is cheap. Jobs cannot be deleted and don't need to be.
- **Endpoint: billed every hour it exists, including when idle.** Create it on Day 3, warm it before the demo, and delete it after judging: `99_teardown.sh --endpoint-only`. Keep `model.tar.gz` in S3 (§10.5).
- Endpoint configs and models cost nothing. `99_teardown.sh` removes them anyway.

## 7. Check yourself

1. Why does `train.py` read `SM_CHANNEL_TRAIN` with a default value instead of a hard-coded path?
2. If you delete the *Model* but keep the *Endpoint*, does billing stop?
3. Why does BACKBONE pick a real-time endpoint and not a serverless one?

<details><summary>Answers</summary>

1. So the identical script runs locally (default path) and in SageMaker script mode (env var set by SageMaker). This is BACKBONE's "same script local + SageMaker" rule, and G6 reproducibility depends on it.
2. No. The endpoint is the thing running on an instance. Delete the endpoint to stop billing.
3. G6 requires p95 < 300 ms during a live demo, and §14 lists cold start as a risk. Serverless scales to zero and cold-starts. Real-time with 1 warm instance does not.
</details>
