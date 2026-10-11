# AquaAgent — System and AWS Architecture

> How AquaAgent is built and how it runs on AWS: components, request flow, data/ML pipeline, every AWS service and why, security, cost and operations.
> Contracts: [BACKBONE.md](../BACKBONE.md). Models and results: [AI_ML.md](AI_ML.md). Step-by-step commands: [RUNBOOK.md](RUNBOOK.md). Status: 2026-10-11.
> Account IDs, image URIs and model IDs are never written in code or docs — scripts read them from `infra/env.sh`, `infra/.state/` and SSM.

---

## 1. System architecture

### 1.1 Components
| Layer | Component | Tech | Responsibility |
|---|---|---|---|
| UI | **Frontend** | React + Vite + Tailwind, zustand | Landing page, `/simulate` (plan view, controls, inspector, AI monitor, EXPLAIN WHY, guided tour), `/city` concept demo. Renders API values only (no hydraulics, no ground truth — enforced by lint guards). |
| Edge | **API Gateway (HTTP API)** | AWS | Public HTTPS endpoint, throttling (25 req/s, burst 50), proxies to the ALB. |
| Orchestrator | **api** container `:8080` | FastAPI | Owns the simulation session, applies user events (taps, leaks, bursts, valves), strips ground truth (firewall), keeps the `SensorWindow` buffer, runs the **AI monitor** (calls predictor + detector every step), freezes incidents, runs the **Bedrock agent**. API key + CORS checks. |
| Physics | **sim** container `:8000` | WNTR 1.5.0 (EPANET 2.2) | Steps the EPA tutorial network in 300-s steps; leaks/bursts on pre-split pipes; sessions with LRU + per-session lock. |
| ML | **predictor** container `:8001` | PyTorch (CPU) | Edge-aware GATv2: reconstruction + 5-sensor leave-one-out (§7.9). Loads `model.tar.gz` from S3 by version. Rejects ground-truth fields (422). |
| ML | **detector** container `:8002` | PyTorch (CPU) | SensorSetNet anomaly detector + physics-signature localiser. Loads artifacts from S3 with SHA-256 check. |
| GenAI | **Amazon Bedrock** | Nova Lite (Converse) | Grounded incident report via a tool loop (called by the api container). |
| Data/ML | **S3, ECS Fargate Spot, SageMaker** | AWS | Dataset generation, features, training, artifact storage (offline path). |

### 1.2 Runtime view (one request)
```
 Browser (Amplify-hosted SPA)
    │  HTTPS  + X-Api-Key, Origin = Amplify domain
    ▼
 API Gateway HTTP API ($default stage, throttle 25/s burst 50)
    │  HTTP
    ▼
 Application Load Balancer :80  ──► target group (ip, HTTP:8080, health /api/health)
    │
    ▼
 ┌──────────────────────── ECS Fargate task "aquaagent-serve" (2 vCPU / 4 GB, awsvpc) ────────────────────────┐
 │                                                                                                            │
 │   api :8080 ──HTTP localhost──► sim :8000          (advance N steps, apply events, snapshots)             │
 │      │                                                                                                     │
 │      ├──HTTP localhost──► predictor :8001          (SensorWindow → expected values + LOO)                 │
 │      ├──HTTP localhost──► detector  :8002          (residual frame → status, P(anomaly), candidates/zone) │
 │      └──HTTPS──► Amazon Bedrock (Nova Lite)        (only on EXPLAIN WHY; tools read the frozen incident)  │
 │                                                                                                            │
 │   predictor & detector read model artifacts from S3 at start-up (versions from SSM)                        │
 └────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```
Per simulator tick (e.g. 20 steps at 20×): the api advances the sim, converts each snapshot to sensor readings with the noise model, appends to the `SensorWindow`, calls the predictor and detector for every step, updates `/api/ai/state`. Measured: p50 0.58 s per 20-step tick end to end through API Gateway.

### 1.3 Firewall (BACKBONE §11)
Ground truth (leak positions, hidden node states, scenario specs) exists only inside the sim and the dataset tables. The api forwards only sensor readings + SCADA context (`SensorWindow`) to models and agent tools, and the frontend receives the public `NetworkView` and AI state. Tests in modules 02/04/08 and the frontend lint guard enforce it.

### 1.4 Offline data and ML pipeline
```
 config/generation/ds3.yaml (in the sim image)
        │
        ▼
 ECS RunTask × 24  (Fargate Spot, sim image "generate --shard i")  ──► s3://…/raw/ds3/shard=i/*.parquet
        │
        ▼
 ECS RunTask merge (4 vCPU / 16 GB)  ──► s3://…/processed/ds3/split=train|val|test/… + manifest.json
        │
        ▼
 SageMaker job: features   (ml.r6i.2xlarge Spot)  ──► s3://…/features/ds3/{train,val,test}.npz, scalers, graph
        │
        ▼
 SageMaker job: predictor  (ml.g4dn.xlarge Spot GPU) ──► s3://…/models/predictor/gnn_ds3_…/model.tar.gz
        │
        ▼
 SageMaker job: detector   (ml.g4dn.xlarge Spot GPU) ──► s3://…/models/anomaly/thr_ds3_…/{model.pt,detector.json}
        │                                                   + experiments/ (test metrics, ds1 baseline on same test)
        ▼
 SageMaker job: signatures (ml.c5.2xlarge Spot, WNTR) ──► s3://…/models/localisation/sig_ds3_…/signatures.json
        │
        ▼
 SSM params (AQUA_PREDICTOR_VERSION, AQUA_THRESHOLDS_URI, AQUA_SIGNATURES_URI)  ──► new ECS task revision
```

---

## 2. AWS services used

Region **ap-south-1 (Mumbai)**; everything tagged `project=aquaagent`; everything created by idempotent terminal scripts `infra/scripts/NN_*.sh` (`set -euo pipefail`, logs in `infra/logs/`).

| Service | What we use | Script |
|---|---|---|
| **AWS Budgets** | $10/month budget with e-mail alert | `01_budget_alert.sh` |
| **Amazon S3** | One bucket `aquaagent-<account>-ap-south-1`: versioned, private, public access blocked, lifecycle (non-current versions 7 d, abort multipart 1 d) | `02_s3_bucket.sh` |
| **IAM** | 5 least-privilege roles (§3) | `03_iam_roles.sh` |
| **Amazon ECR** | `aquaagent-sim`, `aquaagent-api`, `aquaagent-predictor` (predictor image also runs the detector) | `04_ecr_repos.sh`, `05_build_push_images.sh` |
| **CodeBuild** | Fallback image builder when Docker is unavailable | `codebuild_image.sh` |
| **Amazon ECS on Fargate / Fargate Spot** | Cluster `aquaagent` with both capacity providers; batch datagen tasks (Spot) and the always-on serve service | `06_ecs_cluster.sh`, `07_run_datagen.sh`, `09_ecs_service.sh` |
| **Elastic Load Balancing (ALB)** | Internet-facing ALB, listener :80 → target group (ip, 8080), health `/api/health`, idle timeout 60 s | `08_network_alb.sh` |
| **Amazon API Gateway (HTTP API)** | Public HTTPS URL, `$default` auto-deploy stage, throttle 25 req/s / burst 50 | `10_apigw_https.sh` |
| **SSM Parameter Store** | Runtime config injected into the task: `AQUA_API_KEY` (SecureString), `AQUA_AGENT`, `AQUA_BEDROCK_MODEL_ID`, `AQUA_CORS_ORIGINS`, `AQUA_PREDICTOR_VERSION`, `AQUA_THRESHOLDS_URI`, `AQUA_SIGNATURES_URI` | `11_ssm_params.sh` |
| **Amazon SageMaker** | Training Jobs (script mode, AWS PyTorch 2.8 containers, managed Spot) for features, GNN, detector, signatures | `12_sagemaker_train.sh` → `ml/sagemaker/launch_training.py` |
| **Amazon Bedrock** | Converse API, Amazon Nova Lite via APAC inference profile | `14_bedrock_check.sh` |
| **AWS Amplify Hosting** | Static SPA, manual zip deployments (no Git connection), SPA rewrite | `17_amplify_manual.sh` |
| **CloudWatch Logs** | `/ecs/aquaagent-{api,sim,predictor,datagen}` (detector streams under `/ecs/aquaagent-predictor`), `/aws/sagemaker/TrainingJobs` | in task defs |
| **Default VPC** | Default subnets (recreated), security groups below; public IPs for ECR/S3 access (no NAT gateway cost) | `06_ecs_cluster.sh`, `08_network_alb.sh` |

### 2.1 S3 layout (BACKBONE §10.2)
| Prefix | Content |
|---|---|
| `configs/` | network + generation configs |
| `raw/<ds>/shard=i/` | per-shard parquet from datagen |
| `processed/<ds>/` | merged, split tables + `manifest.json` (ds1: 1,200 sims, ds3: 12,000) |
| `features/<ds>/` | `{train,val,test}.npz`, `scalers.json`, `graph.json`, `residuals/` |
| `models/predictor/<mv>/model.tar.gz` | model.pt + meta.json + scalers.json + graph.json |
| `models/anomaly/<thr>/` | `model.pt` + `detector.json` (σ, τ, T, content SHA-256) |
| `models/localisation/<sig>/signatures.json` | physics signatures |
| `experiments/<version>/` | metrics, curves, tables, plots |
| `sagemaker/` | job code bundles, job output, staged inputs (`data/`), run scratch (`runs/`) |

### 2.2 Serve task definition (`infra/ecs/task-definition.json.tpl`)
| Container | Image | Port | Notes |
|---|---|---|---|
| sim | `aquaagent-sim` | 8000 | health check; WNTR |
| predictor | `aquaagent-predictor` | 8001 | `AQUA_PREDICTOR_VERSION` from SSM; loads from S3 |
| detector | `aquaagent-predictor` (detector entry) | 8002 | `AQUA_THRESHOLDS_URI`, `AQUA_SIGNATURES_URI` from SSM |
| api | `aquaagent-api` | 8080 | depends on the other three; API key, CORS, Bedrock settings from SSM; `AQUA_PREDICTOR_URL`/`AQUA_DETECTOR_URL` = localhost |
Task: 2 vCPU / 4 GB, Fargate, desired count 1. Current revision `aquaagent-serve:4`, images tagged `dev-202610101506`.

---

## 3. Security

| Control | Implementation |
|---|---|
| Public surface | Only API Gateway (HTTPS) and Amplify (HTTPS). |
| Authentication | `X-Api-Key` header checked by the api in AWS mode (key in SSM SecureString, baked into the Amplify build); `/api/health` open for the ALB. |
| CORS | Allowed origin = the Amplify domain only (`AQUA_CORS_ORIGINS`). |
| Network | Task security group accepts **8080 only from the ALB security group**; containers talk over localhost inside the task. |
| IAM: `aqua-ecs-exec` | pull images, write logs, `ssm:GetParameters` on `/aquaagent/*` + KMS decrypt (secret injection). |
| IAM: `aqua-sim-task` | S3 read/write `configs/`, `raw/`, `processed/` only; no delete, no Bedrock, no SageMaker. |
| IAM: `aqua-api-task` | S3 read `models/`; `bedrock:InvokeModel*` on the Nova Lite APAC profile + its model ARNs; `sagemaker:InvokeEndpoint` on our endpoint name. |
| IAM: `aqua-sagemaker-exec` | S3 read `features/`, `models/`, `sagemaker/`; write `models/`, `experiments/`, `sagemaker/`; ECR pull; logs. |
| IAM: `aqua-codebuild` | optional image builds. |
| Data | Bucket private + versioned; artifacts hash-checked on load; no secrets or account IDs in the repo. |
| AI safety | Firewall (no ground truth to models/agent); grounding check on every number in Bedrock reports; deterministic fallback. |

---

## 4. Cost (measured / expected)

| Item | When | Cost |
|---|---|---|
| ECS serve task (2 vCPU / 4 GB Fargate) + ALB | while running | ≈ $3 / day |
| ALB alone | while the service is parked | ≈ $0.60 / day |
| Datagen ds3 (24 Spot tasks ≈ 7 min + merge) | once | cents |
| SageMaker ds3 jobs (all Spot; GNN 1,118 billable s on g4dn.xlarge, features 61 s) | once | < $1 |
| Bedrock Nova Lite report | per EXPLAIN WHY | ≈ $0.0003 |
| S3, ECR, logs | idle | < $0.10 / month |
Budget alert at $10/month.

## 5. Operations

| Task | Command |
|---|---|
| Status at a glance | `make status` (`infra/scripts/90_status.sh`) |
| Park (stop the task, keep everything) | `infra/scripts/09_ecs_service.sh --scale 0` |
| Resume | `infra/scripts/09_ecs_service.sh --scale 1` (≈ 2–3 min) |
| Deploy new images / models | `IMAGE_TAG=<tag> infra/scripts/05_build_push_images.sh` → update `infra/.state/{predictor_version,thresholds_uri,signatures_uri}` → `11_ssm_params.sh` → `09_ecs_service.sh` |
| Generate a dataset on ECS | `AQUA_DATASET_VERSION=ds3 MERGE_CPU=4096 MERGE_MEMORY=16384 infra/scripts/07_run_datagen.sh 24` |
| Train on SageMaker | `python -m ml.sagemaker.launch_training --task predictor\|features\|detector\|signatures --dataset-version ds3 --instance-type … --channel name=s3://… --wait` |
| Deploy the frontend | `infra/scripts/17_amplify_manual.sh deploy` |
| Logs | `aws logs tail /ecs/aquaagent-api --since 15m` (also `-sim`, `-predictor`) |
| Rollback models to ds1 | set the three state files to `gnn_ds1_202610090559`, `thr_ds1_202610091624`, `sig_ds1_202610091648` → `11_ssm_params.sh` → `09_ecs_service.sh` |
| Full teardown | `infra/scripts/99_teardown.sh` (asks for confirmation; keeps S3 unless `--purge`) |

## 6. Design decisions
1. **One ECS task, four containers on localhost** — lowest latency and cost for a demo; models as separate containers keep torch out of the api image and mirror the SageMaker endpoint contract (`/ping`, `/invocations`) so a real-time endpoint is a drop-in.
2. **API Gateway in front of the ALB** — free HTTPS and throttling without a certificate/domain.
3. **Fargate Spot for batch, SageMaker managed Spot for training** — 55–70 % cheaper; jobs are idempotent and short.
4. **Training on SageMaker, serving on ECS** — training scales (GPU, 10× data) while serving stays a single always-on task; no idle endpoint bill.
5. **Bedrock Nova Lite** — 7/7 grounded on recorded incidents in one call at ≈ $0.0003/report; Anthropic models blocked by the account's payment method.
6. **Amplify manual deploy** — no repository connection needed.
7. **SSM for every version/URI** — model swaps are config + a new task revision, no code change.
