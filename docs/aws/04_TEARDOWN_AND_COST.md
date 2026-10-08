# 04 — Teardown and Cost

> BACKBONE §10.5: Budget alert on Day 1 · smallest endpoint that passes G6 · **delete the endpoint after judging** (keep `model.tar.gz`) · ECS `desiredCount=0` outside demo windows · tag everything `project=aquaagent`.

## 1. What costs money while idle

| Resource | Idle cost? | Rough driver | How to stop it |
|---|---|---|---|
| **SageMaker real-time endpoint** | **Yes, the biggest** | instance-hours, 24/7 while it exists | `infra/scripts/99_teardown.sh --endpoint-only` |
| **ALB** | Yes | hourly + LCU | full teardown (or keep during the event) |
| **Fargate service task** (`desiredCount=1`) | Yes | vCPU-h + GB-h (1 vCPU / 2 GB, D10) | `infra/scripts/09_ecs_service.sh --scale 0` |
| NAT gateway | **None in our design** | — | we use public subnets + `assignPublicIp=ENABLED` on purpose |
| Public IPv4 address on the task | small, hourly | per public IP | scale to 0 |
| API Gateway HTTP API | No (per request) | requests | — |
| Amplify Hosting | ~No | build minutes + GB served | — |
| S3 / ECR storage | tiny | GB-month (versioning keeps old versions) | `--purge` at the very end |
| CloudWatch Logs | tiny | GB ingested (14-day retention set) | deleted in teardown |
| SSM standard parameters | No | — | — |
| Bedrock | No (per token) | tokens | — |
| SageMaker training job | No (only while running) | instance-seconds | — |

Check spend at any time with `make status` (the budget row shows actual vs limit).

## 2. Daily parking (during the hackathon)

```bash
infra/scripts/09_ecs_service.sh --scale 0      # night: stop the Fargate task
infra/scripts/09_ecs_service.sh --scale 1      # morning: start it (≈2–4 min to healthy)
```
Create the endpoint only on Day 3 (schedule §13), and delete it if you stop working on it for hours. Re-deploying from the same `model.tar.gz` takes about 5–10 minutes.

## 3. Teardown order (what `99_teardown.sh` does)

1. **SageMaker endpoint**, then endpoint configs, then models. The endpoint goes first because it is the most expensive.
2. ECS service (scale 0, then delete), then deregister task definitions.
3. API Gateway HTTP API.
4. ALB listener, then the ALB (wait until it is deleted), then the target group, then the security groups (retried while ENIs drain).
5. ECS cluster, then log groups.
6. ECR repos (`--force`), SSM parameters, Amplify app, CodeBuild project.
7. IAM roles (inline policies deleted, managed policies detached, then the role).
8. Budget, deleted last so it watches the teardown.
9. S3 bucket **only with `--purge`**. All object versions and delete markers are removed first.

```bash
# right after judging (keeps everything except the endpoint)
infra/scripts/99_teardown.sh --endpoint-only
# end of event (keeps S3: dataset, model.tar.gz, experiments/, demo video)
make teardown
# final cleanup, irreversible
make teardown ARGS=--purge
# verify
make status          # every row "-"
aws resourcegroupstaggingapi get-resources --tag-filters Key=project,Values=aquaagent --query 'ResourceTagMappingList[].ResourceARN'
```

## 4. Check yourself

1. Which single command removes the most idle cost right after judging?
2. Why does the design have no NAT gateway, and what replaces it?
3. What does `make teardown` deliberately leave behind, and why?

<details><summary>Answers</summary>

1. `infra/scripts/99_teardown.sh --endpoint-only`, which deletes the SageMaker endpoint (§10.5).
2. A NAT gateway bills hourly. Our tasks run in default-VPC public subnets with `assignPublicIp=ENABLED`, which lets them reach ECR, S3, SageMaker and Bedrock directly. Their security group only allows inbound traffic from the ALB.
3. The S3 bucket: the dataset, `model.tar.gz`, `experiments/` and the demo video. These are the evidence behind every pitch number (§16), so they are only deleted with `--purge`.
</details>
