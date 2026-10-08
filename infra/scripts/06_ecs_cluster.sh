#!/usr/bin/env bash
# =============================================================================
# 06_ecs_cluster.sh — Fargate cluster + CloudWatch log groups
# BACKBONE:      §3.2 (ECS Fargate, CloudWatch Logs)
# Prerequisites: 00 passes
# Creates:       default-VPC public subnets if missing (free); ECS cluster $ECS_CLUSTER (FARGATE + FARGATE_SPOT)
#                log groups $LOG_GROUP_API, $LOG_GROUP_SIM, $LOG_GROUP_DATAGEN (14-day retention)
# Verify:        aws ecs describe-clusters --clusters "$ECS_CLUSTER" --query 'clusters[0].status'
#                aws logs describe-log-groups --log-group-name-prefix /ecs/aquaagent
# Undo:          99_teardown.sh
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account

# Fargate tasks need public default subnets (no NAT = no NAT cost). Recreate them if the default VPC has none.
if [[ -z "$(default_subnets_csv)" ]]; then
  for az in $(aws ec2 describe-availability-zones --query 'AvailabilityZones[?State==`available`].ZoneName' --output text | tr '\t' '\n' | head -2); do
    aws ec2 create-default-subnet --availability-zone "$az" --query 'Subnet.SubnetId' --output text
  done
  ok "default subnets created: $(default_subnets_csv)"
else
  ok "default subnets present: $(default_subnets_csv)"
fi

# First ECS use in an account needs the ECS service-linked role (free).
aws iam get-role --role-name AWSServiceRoleForECS >/dev/null 2>&1 \
  || { aws iam create-service-linked-role --aws-service-name ecs.amazonaws.com >/dev/null && ok "ECS service-linked role created"; sleep 10; }

STATUS="$(aws ecs describe-clusters --clusters "$ECS_CLUSTER" --query 'clusters[0].status' --output text 2>/dev/null || true)"
if [[ "$STATUS" == "ACTIVE" ]]; then
  ok "cluster $ECS_CLUSTER exists"
else
  aws ecs create-cluster --cluster-name "$ECS_CLUSTER" --capacity-providers FARGATE FARGATE_SPOT \
    --default-capacity-provider-strategy capacityProvider=FARGATE_SPOT,weight=1 \
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
  aws logs put-retention-policy --log-group-name "$lg" --retention-in-days 7
done
