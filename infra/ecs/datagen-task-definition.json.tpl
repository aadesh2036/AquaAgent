{
  "family": "${TASKDEF_FAMILY_DATAGEN}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "${ECS_TASK_CPU}",
  "memory": "${ECS_TASK_MEMORY}",
  "executionRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_ECS_EXEC}",
  "taskRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_SIM_TASK}",
  "runtimePlatform": {"cpuArchitecture": "X86_64", "operatingSystemFamily": "LINUX"},
  "containerDefinitions": [
    {
      "name": "sim",
      "image": "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_SIM}:${IMAGE_TAG}",
      "essential": true,
      "command": ["generate", "--help"],
      "environment": [
        {"name": "AQUA_MODE", "value": "aws"},
        {"name": "AQUA_REGION", "value": "${AWS_REGION}"},
        {"name": "AQUA_BUCKET", "value": "${AQUA_BUCKET}"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {"awslogs-group": "${LOG_GROUP_DATAGEN}", "awslogs-region": "${AWS_REGION}", "awslogs-stream-prefix": "datagen"}
      }
    }
  ],
  "tags": [{"key": "${PROJECT_TAG_KEY}", "value": "${PROJECT_TAG_VALUE}"}]
}
