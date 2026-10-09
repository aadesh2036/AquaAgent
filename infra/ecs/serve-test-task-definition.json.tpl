{
  "family": "${TASKDEF_FAMILY_SERVE_TEST}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": [
    "FARGATE"
  ],
  "cpu": "${ECS_TASK_CPU}",
  "memory": "${ECS_TASK_MEMORY}",
  "executionRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_ECS_EXEC}",
  "taskRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_API_TASK}",
  "runtimePlatform": {
    "cpuArchitecture": "X86_64",
    "operatingSystemFamily": "LINUX"
  },
  "containerDefinitions": [
    {
      "name": "sim",
      "image": "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_SIM}:${IMAGE_TAG}",
      "essential": true,
      "command": [
        "serve",
        "--port",
        "8000"
      ],
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "AQUA_MODE",
          "value": "aws"
        },
        {
          "name": "AQUA_REGION",
          "value": "${AWS_REGION}"
        },
        {
          "name": "AQUA_NETWORK_ID",
          "value": "${AQUA_NETWORK_ID}"
        }
      ],
      "healthCheck": {
        "command": [
          "CMD-SHELL",
          "python -c \"import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/sim/health',timeout=3).status==200 else 1)\""
        ],
        "interval": 15,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 30
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "${LOG_GROUP_SIM}",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "sim"
        }
      }
    },
    {
      "name": "predictor",
      "image": "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_PREDICTOR}:${IMAGE_TAG}",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8001,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "AQUA_REGION",
          "value": "${AWS_REGION}"
        },
        {
          "name": "AQUA_BUCKET",
          "value": "${AQUA_BUCKET}"
        },
        {
          "name": "AQUA_PREDICTOR_VERSION",
          "value": "${AQUA_PREDICTOR_VERSION}"
        }
      ],
      "healthCheck": {
        "command": [
          "CMD-SHELL",
          "python -c \"import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8001/predictor/health',timeout=3).status==200 else 1)\""
        ],
        "interval": 15,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "${LOG_GROUP_PREDICTOR}",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "predictor"
        }
      }
    },
    {
      "name": "api",
      "image": "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_API}:${IMAGE_TAG}",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "dependsOn": [
        {
          "containerName": "sim",
          "condition": "HEALTHY"
        },
        {
          "containerName": "predictor",
          "condition": "HEALTHY"
        }
      ],
      "environment": [
        {
          "name": "AQUA_MODE",
          "value": "aws"
        },
        {
          "name": "AQUA_REGION",
          "value": "${AWS_REGION}"
        },
        {
          "name": "AQUA_BUCKET",
          "value": "${AQUA_BUCKET}"
        },
        {
          "name": "AQUA_NETWORK_ID",
          "value": "${AQUA_NETWORK_ID}"
        },
        {
          "name": "AQUA_SENSOR_LAYOUT_ID",
          "value": "${AQUA_SENSOR_LAYOUT_ID}"
        },
        {
          "name": "AQUA_SIM_URL",
          "value": "http://localhost:8000"
        },
        {
          "name": "AQUA_PREDICTOR_ENDPOINT",
          "value": "${AQUA_PREDICTOR_ENDPOINT}"
        },
        {
          "name": "AQUA_PREDICTOR_URL",
          "value": "http://localhost:8001"
        },
        {
          "name": "AQUA_AGENT",
          "value": "template"
        },
        {
          "name": "AQUA_PREDICTOR_VERSION",
          "value": "${AQUA_PREDICTOR_VERSION}"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "${LOG_GROUP_API}",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "api"
        }
      }
    }
  ],
  "tags": [
    {
      "key": "${PROJECT_TAG_KEY}",
      "value": "${PROJECT_TAG_VALUE}"
    },
    {
      "key": "purpose",
      "value": "test"
    }
  ]
}
