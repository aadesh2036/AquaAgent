#!/usr/bin/env bash
# =============================================================================
# 06_ecs_cluster.sh — Fargate cluster + CloudWatch log groups
# BACKBONE:      §3.2 (ECS Fargate, CloudWatch Logs)
# Prerequisites: 00 passes
# Creates:       ECS cluster $ECS_CLUSTER (FARGATE capacity provider)
#                log groups $LOG_GROUP_API, $LOG_GROUP_SIM, $LOG_GROUP_DATAGEN (14-day retention)
# Verify:        aws ecs describe-clusters --clusters "$ECS_CLUSTER" --query 'clusters[0].status'
#                aws logs describe-log-groups --log-group-name-prefix /ecs/aquaagent
# Undo:          99_teardown.sh
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account

STATUS="$(aws ecs describe-clusters --clusters "$ECS_CLUSTER" --query 'clusters[0].status' --output text 2>/dev/null || true)"
if [[ "$STATUS" == "ACTIVE" ]]; then
  ok "cluster $ECS_CLUSTER exists"
else
  aws ecs create-cluster --cluster-name "$ECS_CLUSTER" --capacity-providers FARGATE \
    --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1 \
    --tags "$TAG_CLI_LOWER" >/dev/null
  ok "cluster $ECS_CLUSTER created"
fi

for lg in "$LOG_GROUP_API" "$LOG_GROUP_SIM" "$LOG_GROUP_DATAGEN"; do
  if [[ "$(aws logs describe-log-groups --log-group-name-prefix "$lg" --query "logGroups[?logGroupName=='$lg'] | length(@)" --output text)" == "0" ]]; then
    aws logs create-log-group --log-group-name "$lg" --tags "${PROJECT_TAG_KEY}=${PROJECT_TAG_VALUE}"
    ok "log group $lg created"
  else
    ok "log group $lg exists"
  fi
  aws logs put-retention-policy --log-group-name "$lg" --retention-in-days 14
done
