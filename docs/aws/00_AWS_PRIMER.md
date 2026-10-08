# 00 — AWS Primer for AquaAgent

> For someone who knows Python/ML but has never deployed to AWS.
> Read this before `docs/aws/01_SAGEMAKER_PRIMER.md` and `02_BEDROCK_PRIMER.md`.
> Contracts are owned by [BACKBONE.md](../../BACKBONE.md) (§3.2 deployment, §10 resources). This primer explains them; it does not redefine them.

## 1. Mental model in one diagram

```
 YOU (terminal: CloudShell or laptop with AWS CLI v2)
   │  aws ... commands, authenticated as an IAM identity in ONE account, ONE region (§10.1)
   ▼
┌──────────────────────────────── AWS account ─────────────────────────────────┐
│ Region us-east-1 (default, D1)                                               │
│                                                                              │
│  Amplify Hosting ── serves React build over HTTPS ──▶ browser                │
│       │ fetch(VITE_API_BASE_URL + /api/...)                                  │
│       ▼                                                                      │
│  API Gateway HTTP API (HTTPS) ──proxy──▶ ALB (HTTP :80) ──▶ ECS Fargate task │
│                                                         ┌─────────────────┐  │
│                                                         │ api :8080       │  │
│                                                         │   │ localhost    │  │
│                                                         │ sim :8000       │  │
│                                                         └───┬─────┬───────┘  │
│                       IAM task role (no keys!) ─────────────┘     │          │
│                                    ▼                              ▼          │
│                  SageMaker endpoint (predictor)        Bedrock (Claude)      │
│                                    ▲                                         │
│  S3 bucket ── features ──▶ SageMaker Training Job ── model.tar.gz ──┘        │
│     ▲                                                                        │
│     └── ECS RunTask (sim image, `generate`) × 8 shards                       │
│  ECR: container images     CloudWatch Logs: every container + job            │
│  SSM Parameter Store: API key + runtime config   AWS Budgets: cost alarm     │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 2. The concepts that matter here (and nothing more)

| # | Concept | One-line meaning | AquaAgent use |
|---|---|---|---|
| 1 | **Account + region** | Account = billing and security boundary. Region = the data centre group where resources live. | Everything is in ONE region (§10.1). Mixing regions is the most common beginner bug. |
| 2 | **IAM users vs roles** | A *user* has long-lived keys. A *role* is assumed by a service and gets short-lived credentials automatically. | Our code **never contains keys**. ECS tasks, SageMaker and CodeBuild each assume a role (§10.3). Your terminal uses your own user/SSO profile. |
| 3 | **S3** | Object storage with keys like paths. | `s3://aquaagent-<acct>-<region>/` laid out per §10.2: data, features, models, experiments. |
| 4 | **ECR** | Private Docker registry. | `aquaagent-sim`, `aquaagent-api`, image tag = git short SHA. |
| 5 | **ECS Fargate: task definition / task / service** | *Task definition* = a recipe (images, CPU, env, roles). *Task* = one running copy. *Service* = "keep N tasks running and attach them to a load balancer". | One task definition with two containers (`api`, `sim`), run by a **service** with `desiredCount=1`. Data generation uses one-off **tasks** (`run-task`). |
| 6 | **ALB** | HTTP load balancer with health checks. | Sends traffic to `api:8080` and checks `/api/health`. |
| 7 | **API Gateway HTTP API** | A managed HTTPS front door. | **Mixed content:** Amplify serves the page over HTTPS, and browsers block an HTTPS page from calling a plain-HTTP ALB. API Gateway gives us an HTTPS URL that proxies to the ALB (§3.2) without buying a domain or certificate. |
| 8 | **Amplify Hosting** | Builds and hosts a static frontend from a Git branch. | Builds `frontend/` on every push to `main` and injects `VITE_API_BASE_URL`. |
| — | **CloudWatch Logs** | Where container stdout/stderr goes. | `/ecs/aquaagent-*`, `/aws/sagemaker/*`. Read with `aws logs tail <group> --follow`. |

## 3. Exactly how AquaAgent uses AWS (BACKBONE map)

| BACKBONE | Resource | Created by |
|---|---|---|
| §10.5 | Budget alert | `infra/scripts/01_budget_alert.sh` |
| §10.2 | S3 bucket | `02_s3_bucket.sh` |
| §10.3 | IAM roles | `03_iam_roles.sh` |
| §3.2 | ECR repos, images | `04_ecr_repos.sh`, `05_build_push_images.sh` |
| §3.2 | ECS cluster, logs | `06_ecs_cluster.sh` |
| §8.6 | Data generation tasks | `07_run_datagen.sh` |
| §3.2 | ALB, security groups | `08_network_alb.sh` |
| §3.2 | ECS service (api + sim) | `09_ecs_service.sh` |
| §3.2 | API Gateway | `10_apigw_https.sh` |
| §10.3–10.4 | SSM parameters | `11_ssm_params.sh` |
| §3.2 | SageMaker | `12_…`, `13_…` (see SageMaker primer) |
| §10.1 | Bedrock check | `14_bedrock_check.sh` (see Bedrock primer) |
| §3.2 | Amplify | `15_amplify_app.sh` |

## 4. Commands to run, in order (expected output shape)

```bash
# 0. One-time: configure credentials (laptop). CloudShell already has them.
aws configure sso            # or: aws configure --profile <name>
cp infra/env.sh.example infra/env.sh && $EDITOR infra/env.sh     # set AWS_PROFILE, AWS_REGION, BUDGET_EMAIL

# 1. Who am I? (must print your account + ARN)
aws sts get-caller-identity
# { "UserId": "...", "Account": "<12-digit account id>", "Arn": "arn:aws:iam::<account-id>:user/you" }

# 2. Prerequisites table
make aws-prereqs
# CHECK                        RESULT DETAIL
# aws cli v2                   PASS   2.x.y
# credentials (sts)            PASS   arn:aws:iam::...
# docker daemon                WARN   unavailable → CodeBuild fallback      (fine in CloudShell)

# 3. Bootstrap (budget, bucket, roles, registries)
make aws-bootstrap
# ... OK bucket ready: s3://aquaagent-<acct>-us-east-1

# 4. Status at any time
make status
```

## 5. The five most common errors

| Error text (abridged) | Cause | Fix |
|---|---|---|
| `AccessDenied` / `is not authorized to perform: X on resource: Y` | **Permissions.** Either your user lacks rights, or a *role* lacks a statement. | Read the action (`X`) and resource (`Y`) in the message. If the role is ours, add the statement to `infra/iam/<role>.policy.json.tpl` and re-run `03_iam_roles.sh`. |
| `Could not connect to the endpoint URL`, or a resource "not found" that you know exists | **Region.** You are looking in the wrong region. | `echo $AWS_REGION`. All scripts read it from `infra/env.sh`. Never pass `--region` by hand. |
| `ResourceLimitExceeded` / `LimitExceededException` | **Quota.** For example, the SageMaker instance quota is 0 for that type. | `aws service-quotas list-service-quotas --service-code sagemaker --query "Quotas[?contains(QuotaName,'<type>')]"`, then pick another type or request an increase. Increases can take hours, so check on Day 1. |
| `AccessDeniedException … model access` (Bedrock) | **Model access** not enabled. | MANUAL STEP in `14_bedrock_check.sh`. See the Bedrock primer. |
| `CannotPullContainerError` / `manifest unknown` | **Image URI.** The tag is not pushed, the repo name is wrong, or the task has no route to ECR. | `aws ecr describe-images --repository-name aquaagent-api`. Re-run `05_build_push_images.sh`. Our services use `assignPublicIp=ENABLED` because there is no NAT. |

## 6. Cost notes and what to delete

Billed **while idle**: the SageMaker endpoint (largest), the ALB, and running Fargate tasks (service `desiredCount=1`). There is no NAT gateway in this design, on purpose. Close to free when idle: S3, ECR storage, API Gateway (pay per request), Amplify (build minutes plus hosting), SSM standard params, CloudWatch Logs (small).
See [04_TEARDOWN_AND_COST.md](04_TEARDOWN_AND_COST.md). The short version is `infra/scripts/99_teardown.sh --endpoint-only` right after judging, then a full teardown.

## 7. Full deployment (BACKBONE §3.2)

```
GitHub(main) ──▶ Amplify build ──▶ https://main.<id>.amplifyapp.com
                                         │ HTTPS (X-Api-Key)
                                         ▼
                       https://<api-id>.execute-api.<region>.amazonaws.com
                                         │ HTTP proxy  ANY /{proxy+}
                                         ▼
                                ALB :80 ─ TG (ip, :8080, /api/health)
                                         ▼
               ECS service aquaagent-api (Fargate, desired=1, public IP, default VPC)
                ┌──────────── task: aquaagent-serve ─────────────┐
                │  api (FastAPI :8080) ──localhost──▶ sim (:8000) │
                └──────┬───────────────────────┬──────────────────┘
          InvokeEndpoint│                       │Converse (toolConfig)
                        ▼                       ▼
         SageMaker endpoint aquaagent-predictor   Bedrock Claude (AQUA_BEDROCK_MODEL_ID)
```

## 8. Check yourself

1. Why is there an API Gateway in front of an ALB, when the ALB already accepts HTTP requests?
2. Where do the ECS containers get their AWS credentials from, given there are no keys anywhere?
3. What is the difference between `aws ecs run-task` (script 07) and an ECS *service* (script 09)?

<details><summary>Answers</summary>

1. Mixed content. The Amplify page is served over HTTPS, and browsers block calls from it to a plain-HTTP origin. API Gateway gives us a free HTTPS URL that proxies to the ALB (§3.2). It also adds throttling (BI-13).
2. From the **task role** (`aqua-api-task` / `aqua-sim-task`). ECS injects short-lived credentials that the AWS SDK picks up automatically (§10.3).
3. `run-task` starts one-off tasks that exit when done (data generation shards). A service keeps `desiredCount` tasks running, replaces any that die, and registers them with the ALB target group.
</details>
