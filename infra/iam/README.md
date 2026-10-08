# infra/iam — one role per actor (BACKBONE §10.3)

| Role | Trust file | Inline policy template | Managed policy |
|---|---|---|---|
| `aqua-ecs-exec` | `trust-ecs-tasks.json` | `aqua-ecs-exec.policy.json.tpl` (SSM read for secrets — BI-10) | `AmazonECSTaskExecutionRolePolicy` (ECR pull + logs) |
| `aqua-sim-task` | `trust-ecs-tasks.json` | `aqua-sim-task.policy.json.tpl` | — |
| `aqua-api-task` | `trust-ecs-tasks.json` | `aqua-api-task.policy.json.tpl` | — |
| `aqua-sagemaker-exec` | `trust-sagemaker.json` | `aqua-sagemaker-exec.policy.json.tpl` | — |
| `aqua-codebuild` (optional, BI-10) | `trust-codebuild.json` | `aqua-codebuild.policy.json.tpl` | — |
| Amplify service role | — | — | Not created: Amplify static hosting works without one (BACKBONE §10.3 "default") |

`${VAR}` placeholders are rendered from `infra/env.sh` by `lib.sh::render`. `BEDROCK_RESOURCE_ARNS_JSON`
is computed by `03_iam_roles.sh`. It starts as the Anthropic foundation-model wildcard plus this account's
inference profiles, and narrows to the exact ARNs once `14_bedrock_check.sh` has discovered the model (BI-05).
Re-run `03_iam_roles.sh` after script 14 to tighten it.
