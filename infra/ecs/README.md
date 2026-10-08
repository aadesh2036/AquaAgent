# infra/ecs — task definition and service templates (BACKBONE §3.2)

- `task-definition.json.tpl`: the **serve** task. It is ONE task with TWO containers, `sim` :8000 and `api` :8080, which talk over `localhost`. `api` waits for `sim` to be HEALTHY. Secrets and runtime config come from SSM `/aquaagent/*` (script 11).
- `datagen-task-definition.json.tpl`: the **generate** task (same `aquaagent-sim` image, role `aqua-sim-task`). Script 07 overrides the command for each shard.
- `service.json.tpl`: a Fargate service with `desiredCount=1`, in the default VPC with a public IP. There is no NAT gateway, so the public IP is how the task pulls images from ECR. Rendered by script 09.

The two containers share the task role `aqua-api-task`; see BACKBONE_ISSUES BI-11.
