{
  "cluster": "${ECS_CLUSTER}",
  "serviceName": "${ECS_SERVICE}",
  "taskDefinition": "${TASKDEF_ARN}",
  "desiredCount": 1,
  "launchType": "FARGATE",
  "platformVersion": "LATEST",
  "healthCheckGracePeriodSeconds": 90,
  "deploymentConfiguration": {"maximumPercent": 200, "minimumHealthyPercent": 0},
  "networkConfiguration": {
    "awsvpcConfiguration": {
      "subnets": ${SUBNETS_JSON},
      "securityGroups": ["${SG_TASK_ID}"],
      "assignPublicIp": "ENABLED"
    }
  },
  "loadBalancers": [
    {"targetGroupArn": "${TG_ARN}", "containerName": "api", "containerPort": 8080}
  ],
  "propagateTags": "SERVICE",
  "tags": [{"key": "${PROJECT_TAG_KEY}", "value": "${PROJECT_TAG_VALUE}"}]
}
