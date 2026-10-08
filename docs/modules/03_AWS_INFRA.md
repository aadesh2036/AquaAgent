# 03_AWS_INFRA.md
Backbone version: backbone/1.1.0 | Gate: **G3** | Tier: **T2a** (budget + Bedrock check: optional 5-min Day-1 items) | Est. effort: 6 h
Depends on: **gate MVP** (the T1 loop runs locally), 01/08 images | Blocks: 06 (T2b), 07 (T2d), 09 (Amplify) | Schedule slot: Day 3 night / Day 4 AM, only after gate MVP (BACKBONE §13)

> **T2a scope:** deploy the *already working* T1 stack. The predictor runs in-process in the api container (`AQUA_PREDICTOR_ARTIFACT` from S3) and the explanation is the template. No SageMaker, no Bedrock, no ECS datagen in T2a.

> Beginners: read [docs/aws/00_AWS_PRIMER.md](../aws/00_AWS_PRIMER.md) first.

## 1. Purpose
Provision, with terminal-driven idempotent scripts, every AWS resource in BACKBONE §3.2/§10, apart from the SageMaker endpoint itself (module 06) and the Bedrock calls (module 07): budget, S3, IAM, ECR, ECS (cluster, datagen tasks, two-container service), ALB, the API Gateway HTTPS front door, SSM config and Amplify. It also provides one-screen status and an ordered teardown.

## 2. Inputs — contracts consumed
- §3.2 physical deployment, §10.1 region (D1), §10.2 S3 layout, §10.3 IAM roles, §10.4 env var names, §10.5 cost guardrails, D8 (API key), D10 (1 vCPU / 2 GB)
- §7.14.1 (health path `/api/health`, `X-Api-Key`), §8.6 (generate command)
- Images: `sim/Dockerfile` (01), `api/Dockerfile` (08)
- Resolved decisions (BACKBONE 1.1.0): 30-s HTTP API limit (§3.2), inference profiles in IAM (§10.3), exec-role SSM + optional CodeBuild role (§10.3), shared task role accepted (§10.3), FastAPI owns CORS (§3.2), stage throttling (§10.5)

## 3. Outputs — contracts produced
- Resources named in `infra/env.sh.example` (canonical §10 names), all tagged `project=aquaagent`
- `infra/.state/*` (ARNs, DNS, `api_url`, `image_tag`, `bedrock_model_id`, …) consumed by later scripts
- Public HTTPS base URL (API Gateway) = `VITE_API_BASE_URL` (§10.4)
- SSM `/aquaagent/*` = runtime env for the `api` container (§10.4)

## 4. Files owned
`infra/` (all): `env.sh.example`, `scripts/lib.sh`, `scripts/00…15, 90, 99, codebuild_image.sh`, `iam/*.json(.tpl)`, `ecs/*.json.tpl`, `codebuild/buildspec.yml`, `logs/`. Also `amplify.yml`, `docs/aws/*`, `docker-compose.yml`, `.github/workflows/ci.yml`.

## 5. Design decisions (binding)
- **AWS CLI v2 bash scripts**, numbered in run order, idempotent (check-then-create), `set -euo pipefail`, tagged, logged to `infra/logs/<script>_<ts>.log`. *Rejected:* CDK/Terraform (learning curve for a 4-day build), console click-ops (not reproducible).
- **Default VPC, public subnets, `assignPublicIp=ENABLED`, no NAT** (cost). The task SG only accepts :8080 from the ALB SG. *Rejected:* private subnets + NAT (hourly cost, more setup).
- **One task definition, two containers** (`sim` :8000, `api` :8080), `api` dependsOn `sim` HEALTHY, `desiredCount=1` (§3.2). They share the `aqua-api-task` role .
- **API Gateway HTTP API → HTTP_PROXY → ALB** with `ANY /{proxy+}` and `$default` auto-deploy. It is the HTTPS front door that solves mixed content (§3.2). **No APIGW CORS**: FastAPI owns CORS . Stage throttling against a leaked public key . The 30 s integration limit is handled in module 07/08 . *Rejected:* CloudFront (slower to create and propagate), a custom domain + ACM (needs DNS).
- **Secrets/config in SSM** `/aquaagent/*`, injected as ECS `secrets`. The exec role has `ssm:GetParameters` . The API key is generated once with `secrets.token_urlsafe`.
- **Image tag = git short SHA** (§3.2); `docker` if available, else **CodeBuild fallback** (`codebuild_image.sh`, role `aqua-codebuild`).
- **Bedrock IAM**: starts with the Anthropic wildcard and is narrowed to the discovered model/profile ARNs after `14_bedrock_check.sh` .
- **Health check** `/api/health` (§3.2), 15 s interval, 90 s grace. **Logs**: `/ecs/aquaagent-{api,sim,datagen}`, 14-day retention.
- **Teardown order**: endpoint first, S3 kept unless `--purge` (§10.5).

## 6. Implementation plan
| # | Step (≤ 2 h) | Done when |
|---|---|---|
| 1 | `cp infra/env.sh.example infra/env.sh`; set `AWS_PROFILE` (laptop), `AWS_REGION` (D1), `BUDGET_EMAIL`. Run `00_check_prereqs.sh`. | PASS table (docker may be WARN). |
| 2 | `01_budget_alert.sh`; `14_bedrock_check.sh` for **D1/D2** (Day 1 AM, with module 07 owner). | `aws budgets describe-budget …` returns the budget. Script 14 prints "model replied: OK" or the MANUAL STEP is done and re-run. |
| 3 | `02_s3_bucket.sh`, `03_iam_roles.sh`, `04_ecr_repos.sh` (`make aws-bootstrap`). | `aws s3 ls s3://$AQUA_BUCKET/` shows the 7 prefixes; `aws iam get-role --role-name aqua-api-task` OK; both ECR repos exist. |
| 4 | `05_build_push_images.sh` (or `--codebuild` after `03_iam_roles.sh --with-codebuild`). | `aws ecr describe-images --repository-name aquaagent-sim` lists the SHA tag. |
| 5 | `06_ecs_cluster.sh`; upload local ds1 + model artifacts: `aws s3 sync data/processed/ds1 s3://$AQUA_BUCKET/processed/ds1/`, `aws s3 sync data/models s3://$AQUA_BUCKET/models/`. (`07_run_datagen.sh` = T3.) | Cluster ACTIVE; G3 "ds1 + model artifacts in S3": `aws s3 ls s3://$AQUA_BUCKET/models/ --recursive \| head`. |
| 6 | `08_network_alb.sh`; `11_ssm_params.sh`; `09_ecs_service.sh` with the **stub api** (module 08 step 1 provides `/api/health`). | `curl http://$(cat infra/.state/alb_dns)/api/health` → 200; targets `healthy`. |
| 7 | `10_apigw_https.sh` (set `APIGW_THROTTLE_*` first). | **G3:** `curl "$(cat infra/.state/api_url)/api/health"` returns ok from the public internet (try from a phone). |
| 8 | `15_amplify_app.sh` + MANUAL STEP (GitHub). Then re-run `11` + `09` for CORS. `90_status.sh` and a `99_teardown.sh --endpoint-only` dry-run review. | Amplify URL loads (mock UI is fine); `make status` shows every row populated. |

## 7. AWS steps
This whole module is AWS steps. Run order (note: **11 before 09**, because the task definition references SSM):
```bash
make aws-prereqs                          # 00
infra/scripts/01_budget_alert.sh          # Day 1 AM
infra/scripts/14_bedrock_check.sh         # Day 1 AM (D1/D2) — MANUAL STEP if model access needed
make aws-bootstrap                        # 01–04 (01 is idempotent)
make images                               # 05  (CodeBuild fallback if no docker)
bash infra/scripts/06_ecs_cluster.sh       # cluster + log groups
aws s3 sync data/processed/ds1 s3://$AQUA_BUCKET/processed/ds1/ && aws s3 sync data/models s3://$AQUA_BUCKET/models/
infra/scripts/08_network_alb.sh
infra/scripts/11_ssm_params.sh
infra/scripts/09_ecs_service.sh
infra/scripts/10_apigw_https.sh           # → prints HTTPS base URL (G3)
make deploy-frontend                      # 15 — MANUAL STEP: connect GitHub
make status                               # 90
```
**MANUAL STEP boxes:** Bedrock model access (script 14 header) and the Amplify↔GitHub OAuth connection (script 15 header).
**Verify:** `curl "$(cat infra/.state/api_url)/api/health"`; `aws elbv2 describe-target-health --target-group-arn "$(cat infra/.state/tg_arn)"`.
**CORS:** `AQUA_CORS_ORIGINS` (SSM) = the Amplify origin from `infra/.state/amplify_origin`. After script 15, re-run 11 and 09.

## 8. Tests
- **Static (CI):** `bash -n` on every script; `shellcheck -S error`.
- **Idempotency:** run each of 01–11 twice. The second run makes no changes and exits 0 (check the logs in `infra/logs/`).
- **Least privilege:** `aws iam simulate-principal-policy --policy-source-arn arn:aws:iam::$ACCOUNT_ID:role/aqua-sim-task --action-names bedrock:InvokeModel sagemaker:InvokeEndpoint` → `implicitDeny`; the same for `aqua-api-task` with `s3:PutObject` → `implicitDeny`.
- **Secrets grep:** `grep -RInE '[0-9]{12}|AKIA|anthropic\.claude' infra/ docs/` → no hits except placeholders.
- **Firewall:** n/a here (enforced in 02/04/08); infra only ensures `api` is the sole public entry (task SG accepts traffic from the ALB SG only).

## 9. Acceptance gate — G3
Copied from BACKBONE §12, plus module checks:
- [ ] `curl https://<apigw>/api/health` returns ok from the public internet
- [ ] ECS task healthy
- [ ] generate RunTask writes to S3
- [ ] budget alert active
- [ ] (module) every resource in BACKBONE §10 is created by exactly one numbered script and deleted by `99_teardown.sh`
- [ ] (module) scripts are idempotent (second run = no change)
- [ ] (module) no hard-coded account ID, model ID, image URI or secret (grep proof)

## 10. Risks and fallbacks
- Mixed content / CORS (§14 High): API Gateway from Day 2; CORS env in SSM; one CORS owner .
- Bedrock not enabled / needs an inference profile (T2d only): `14_bedrock_check.sh`; `us-east-1` default.
- No docker in CloudShell: CodeBuild fallback, or build on the laptop.
- 30 s API Gateway timeout (not adjustable for HTTP APIs): every request is < 1 s in T1/T2a; T2d Bedrock has a 20-s budget + template fallback.
- **Cut line, end of Day 2 (§13):** if ds1 is not in S3 via ECS, generate locally and `aws s3 sync`.
- Venue Wi-Fi fails (§14 Critical): local `docker compose` stack + fallback video (module 10).

## 11. Handoff
- To **02** (T3 only): `07_run_datagen.sh`, bucket name, `image_tag`.
- To **06**: bucket, `aqua-sagemaker-exec` ARN (`infra/.state/sagemaker_role_arn`), scripts 12/13 wrappers.
- To **07**: `infra/.state/bedrock_model_id`, IAM narrowed after re-running 03, SSM `AQUA_BEDROCK_MODEL_ID`.
- To **08**: task definition template (env/secrets), service, ALB health path, API URL, `X-Api-Key` in SSM.
- To **09**: `VITE_API_BASE_URL` (`infra/.state/api_url`), Amplify app id/origin, `amplify.yml`.
- To **10**: `90_status.sh`, `99_teardown.sh --endpoint-only`, the S3 `demo/` prefix.

## 12. Agent prompt
```
You are implementing module 03 (AWS Infra) of AquaAgent.
Read, in order and completely: INSTRUCTIONS.md, BACKBONE.md, docs/modules/03_AWS_INFRA.md, TILL_NOW.md,
docs/BACKBONE_ISSUES.md rows for module 03, and docs/aws/00_AWS_PRIMER.md. Read nothing else for context.
The scripts in infra/scripts already contain real AWS CLI commands; your job is to execute §6 in order with
the human, fix script bugs you hit (only files in §4), and verify each "done when". Never use the console
except at a documented MANUAL STEP. Never hard-code account IDs, model IDs, image URIs or secrets; mark
uncertain values <VERIFY: …> and add them to docs/RUNBOOK.md "Values to confirm". Every AWS command that
creates cost must be confirmed with the human first. After each step update TILL_NOW.md and STOP.
If a contract is wrong, write it under §13 and stop. Do not create git branches or push.
```

## 13. Proposed Backbone Changes
_(empty)_
