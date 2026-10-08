#!/usr/bin/env bash
# =============================================================================
# 08_network_alb.sh — security groups, ALB, target group (health /api/health), HTTP listener
# BACKBONE:      §3.2 (ALB → target group on api:8080, health /api/health)
# Prerequisites: 00 passes; account has a default VPC (aws ec2 describe-vpcs --filters Name=isDefault,Values=true)
# Creates:       SG $SG_ALB_NAME (80 from internet), SG $SG_TASK_NAME (8080 from ALB SG only)
#                ALB $ALB_NAME (internet-facing), TG $TG_NAME (ip, HTTP:8080), listener :80 → TG
# Verify:        aws elbv2 describe-target-health --target-group-arn "$(cat infra/.state/tg_arn)"
# Undo:          99_teardown.sh
# Cost:          an ALB bills hourly even when idle (see docs/aws/04_TEARDOWN_AND_COST.md)
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account
VPC_ID="$(default_vpc_id)"; [[ "$VPC_ID" != "None" ]] || die "no default VPC in $AWS_REGION"
SUBNETS_SPACE="$(default_subnets_csv | tr ',' ' ')"

ensure_sg() {  # name description → id
  local id
  id="$(aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$VPC_ID" "Name=group-name,Values=$1" --query 'SecurityGroups[0].GroupId' --output text)"
  if [[ "$id" == "None" ]]; then
    id="$(aws ec2 create-security-group --group-name "$1" --description "$2" --vpc-id "$VPC_ID" \
      --tag-specifications "ResourceType=security-group,Tags=[{$TAG_CLI}]" --query GroupId --output text)"
  fi
  printf '%s' "$id"
}
allow_ingress() {  # sg-id port source-args...
  local sg="$1" port="$2"; shift 2
  aws ec2 authorize-security-group-ingress --group-id "$sg" --protocol tcp --port "$port" "$@" >/dev/null 2>&1 || true
}

SG_ALB="$(ensure_sg "$SG_ALB_NAME" "AquaAgent ALB (HTTP from internet; API Gateway proxies here)")"
SG_TASK="$(ensure_sg "$SG_TASK_NAME" "AquaAgent ECS task (8080 from ALB only)")"
allow_ingress "$SG_ALB" 80 --cidr 0.0.0.0/0
allow_ingress "$SG_TASK" 8080 --source-group "$SG_ALB"
state_put sg_alb_id "$SG_ALB"; state_put sg_task_id "$SG_TASK"
ok "security groups: alb=$SG_ALB task=$SG_TASK"

ALB_ARN="$(aws elbv2 describe-load-balancers --names "$ALB_NAME" --query 'LoadBalancers[0].LoadBalancerArn' --output text 2>/dev/null || true)"
if [[ -z "$ALB_ARN" || "$ALB_ARN" == "None" ]]; then
  # shellcheck disable=SC2086
  ALB_ARN="$(aws elbv2 create-load-balancer --name "$ALB_NAME" --type application --scheme internet-facing \
    --subnets $SUBNETS_SPACE --security-groups "$SG_ALB" --tags "$TAG_CLI" \
    --query 'LoadBalancers[0].LoadBalancerArn' --output text)"
  ok "ALB created"
fi
aws elbv2 modify-load-balancer-attributes --load-balancer-arn "$ALB_ARN" \
  --attributes Key=idle_timeout.timeout_seconds,Value=60 >/dev/null
ALB_DNS="$(aws elbv2 describe-load-balancers --load-balancer-arns "$ALB_ARN" --query 'LoadBalancers[0].DNSName' --output text)"

TG_ARN="$(aws elbv2 describe-target-groups --names "$TG_NAME" --query 'TargetGroups[0].TargetGroupArn' --output text 2>/dev/null || true)"
if [[ -z "$TG_ARN" || "$TG_ARN" == "None" ]]; then
  TG_ARN="$(aws elbv2 create-target-group --name "$TG_NAME" --protocol HTTP --port 8080 --vpc-id "$VPC_ID" \
    --target-type ip --health-check-path /api/health --health-check-interval-seconds 15 \
    --healthy-threshold-count 2 --unhealthy-threshold-count 3 --matcher HttpCode=200 --tags "$TAG_CLI" \
    --query 'TargetGroups[0].TargetGroupArn' --output text)"
  ok "target group created"
fi

LISTENER_ARN="$(aws elbv2 describe-listeners --load-balancer-arn "$ALB_ARN" --query 'Listeners[?Port==`80`].ListenerArn | [0]' --output text)"
if [[ "$LISTENER_ARN" == "None" || -z "$LISTENER_ARN" ]]; then
  LISTENER_ARN="$(aws elbv2 create-listener --load-balancer-arn "$ALB_ARN" --protocol HTTP --port 80 \
    --default-actions "Type=forward,TargetGroupArn=$TG_ARN" --tags "$TAG_CLI" \
    --query 'Listeners[0].ListenerArn' --output text)"
  ok "listener :80 created"
fi

state_put alb_arn "$ALB_ARN"; state_put alb_dns "$ALB_DNS"; state_put tg_arn "$TG_ARN"; state_put listener_arn "$LISTENER_ARN"
ok "ALB http://$ALB_DNS  (targets register when 09_ecs_service.sh runs)"
