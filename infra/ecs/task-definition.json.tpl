{
  "family": "${TASKDEF_FAMILY_SERVE}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "${ECS_TASK_CPU}",
  "memory": "${ECS_TASK_MEMORY}",
  "executionRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_ECS_EXEC}",
  "taskRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_API_TASK}",
  "runtimePlatform": {"cpuArchitecture": "X86_64", "operatingSystemFamily": "LINUX"},
  "containerDefinitions": [
    {
      "name": "sim",
      "image": "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_SIM}:${IMAGE_TAG}",
      "essential": true,
      "command": ["serve", "--port", "8000"],
      "portMappings": [{"containerPort": 8000, "protocol": "tcp"}],
      "environment": [
        {"name": "AQUA_MODE", "value": "aws"},
        {"name": "AQUA_REGION", "value": "${AWS_REGION}"},
        {"name": "AQUA_NETWORK_ID", "value": "${AQUA_NETWORK_ID}"}
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "python -c \"import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/sim/health',timeout=3).status==200 else 1)\""],
        "interval": 15, "timeout": 5, "retries": 3, "startPeriod": 30
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {"awslogs-group": "${LOG_GROUP_SIM}", "awslogs-region": "${AWS_REGION}", "awslogs-stream-prefix": "sim"}
      }
    },
    {
      "name": "api",
      "image": "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_API}:${IMAGE_TAG}",
      "essential": true,
      "portMappings": [{"containerPort": 8080, "protocol": "tcp"}],
      "dependsOn": [{"containerName": "sim", "condition": "HEALTHY"}],
      "environment": [
        {"name": "AQUA_MODE", "value": "aws"},
        {"name": "AQUA_REGION", "value": "${AWS_REGION}"},
        {"name": "AQUA_BUCKET", "value": "${AQUA_BUCKET}"},
        {"name": "AQUA_NETWORK_ID", "value": "${AQUA_NETWORK_ID}"},
        {"name": "AQUA_SENSOR_LAYOUT_ID", "value": "${AQUA_SENSOR_LAYOUT_ID}"},
        {"name": "AQUA_SIM_URL", "value": "http://localhost:8000"},
        {"name": "AQUA_PREDICTOR_ENDPOINT", "value": "${AQUA_PREDICTOR_ENDPOINT}"}
      ],
      "secrets": [
        {"name": "AQUA_API_KEY", "valueFrom": "arn:aws:ssm:${AWS_REGION}:${ACCOUNT_ID}:parameter${SSM_PREFIX}/AQUA_API_KEY"},
        {"name": "AQUA_AGENT", "valueFrom": "arn:aws:ssm:${AWS_REGION}:${ACCOUNT_ID}:parameter${SSM_PREFIX}/AQUA_AGENT"},
        {"name": "AQUA_BEDROCK_MODEL_ID", "valueFrom": "arn:aws:ssm:${AWS_REGION}:${ACCOUNT_ID}:parameter${SSM_PREFIX}/AQUA_BEDROCK_MODEL_ID"},
        {"name": "AQUA_PREDICTOR_VERSION", "valueFrom": "arn:aws:ssm:${AWS_REGION}:${ACCOUNT_ID}:parameter${SSM_PREFIX}/AQUA_PREDICTOR_VERSION"},
        {"name": "AQUA_THRESHOLDS_URI", "valueFrom": "arn:aws:ssm:${AWS_REGION}:${ACCOUNT_ID}:parameter${SSM_PREFIX}/AQUA_THRESHOLDS_URI"},
        {"name": "AQUA_SIGNATURES_URI", "valueFrom": "arn:aws:ssm:${AWS_REGION}:${ACCOUNT_ID}:parameter${SSM_PREFIX}/AQUA_SIGNATURES_URI"},
        {"name": "AQUA_CORS_ORIGINS", "valueFrom": "arn:aws:ssm:${AWS_REGION}:${ACCOUNT_ID}:parameter${SSM_PREFIX}/AQUA_CORS_ORIGINS"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {"awslogs-group": "${LOG_GROUP_API}", "awslogs-region": "${AWS_REGION}", "awslogs-stream-prefix": "api"}
      }
    }
  ],
  "tags": [{"key": "${PROJECT_TAG_KEY}", "value": "${PROJECT_TAG_VALUE}"}]
}
