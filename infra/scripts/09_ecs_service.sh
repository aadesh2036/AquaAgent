#!/usr/bin/env bash
# =============================================================================
# 09_ecs_service.sh — register the two-container serve task definition; create/update the service
# BACKBONE:      §3.2 (ONE task, TWO containers api:8080 + sim:8000, desiredCount=1), §10.4 env
# Prerequisites: 03,05,06,08 done AND 11_ssm_params.sh done (task secrets come from SSM)
# Creates:       task definition family $TASKDEF_FAMILY_SERVE (new revision), ECS service $ECS_SERVICE
# Verify:        aws ecs describe-services --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE" \
#                  --query 'services[0].{desired:desiredCount,running:runningCount,status:status}'
#                curl "http://$(cat infra/.state/alb_dns)/api/health"
# Undo:          aws ecs update-service --cluster "$ECS_CLUSTER" --service "$ECS_SERVICE" --desired-count 0
#                (full delete: 99_teardown.sh)
# Usage:         ./09_ecs_service.sh [--scale N]   (--scale 0 parks the service outside demo windows, §10.5)
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account

if [[ "${1:-}" == "--scale" ]]; then
  aws ecs update-service --cluster "$ECS_CLUSTER" --service "$ECS_SERVICE" --desired-count "${2:?count}" >/dev/null
  ok "service scaled to ${2}"; exit 0
fi

aws ssm get-parameter --name "${SSM_PREFIX}/AQUA_API_KEY" >/dev/null 2>&1 || die "SSM params missing — run 11_ssm_params.sh first"

export IMAGE_TAG; IMAGE_TAG="$(state_need image_tag)"
export TG_ARN; TG_ARN="$(state_need tg_arn)"
export SG_TASK_ID; SG_TASK_ID="$(state_need sg_task_id)"
export SUBNETS_JSON; SUBNETS_JSON="$(default_subnets_csv | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read().strip().split(",")))')"

TD_FILE="$(mktemp)"; render "$INFRA_DIR/ecs/task-definition.json.tpl" > "$TD_FILE"
export TASKDEF_ARN
TASKDEF_ARN="$(aws ecs register-task-definition --cli-input-json "file://$TD_FILE" --query 'taskDefinition.taskDefinitionArn' --output text)"
ok "registered $TASKDEF_ARN"

SVC_STATUS="$(aws ecs describe-services --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE" --query 'services[0].status' --output text 2>/dev/null || true)"
if [[ "$SVC_STATUS" == "ACTIVE" ]]; then
  aws ecs update-service --cluster "$ECS_CLUSTER" --service "$ECS_SERVICE" \
    --task-definition "$TASKDEF_ARN" --desired-count 1 --force-new-deployment >/dev/null
  ok "service updated"
else
  SVC_FILE="$(mktemp)"; render "$INFRA_DIR/ecs/service.json.tpl" > "$SVC_FILE"
  aws ecs create-service --cli-input-json "file://$SVC_FILE" >/dev/null
  ok "service created"
fi

log "waiting for service to become stable (can take 3–6 min)…"
aws ecs wait services-stable --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE" \
  || die "not stable — check: aws logs tail $LOG_GROUP_API --since 15m ; aws logs tail $LOG_GROUP_SIM --since 15m"
ALB_DNS="$(state_need alb_dns)"
curl -fsS "http://$ALB_DNS/api/health" && echo && ok "ALB health OK"
