#!/usr/bin/env bash
# =============================================================================
# 16_serve_test_task.sh — ONE-OFF test run of the serve task (sim + predictor + api) without ALB/service
# BACKBONE:      §3.2 (one task, containers over localhost), §7.9 predictor contract; BI-26 (predictor container)
# Purpose:       validate backend containers on ECS one by one BEFORE the production path (08 ALB → 11 SSM →
#                09 service). Fargate Spot, public IP, ingress ONLY from the operator's current IP (/32).
# Prerequisites: 04, 05 (all three images at state image_tag), 06; model.tar.gz in s3://…/models/predictor/<mv>/
# Creates:       SG $SG_TEST_NAME (8080, 8001 from operator /32), task definition $TASKDEF_FAMILY_SERVE_TEST,
#                one running task (state: test_task_arn, test_task_ip, test_api_key — local, gitignored)
# Usage:         ./16_serve_test_task.sh start [--version <model_version>]
#                ./16_serve_test_task.sh smoke      # predictor §7.9 smoke + parity, api /api/health
#                ./16_serve_test_task.sh status
#                ./16_serve_test_task.sh stop       # ALWAYS run when done — the task bills while it runs
# Cost:          Fargate Spot 1 vCPU / 3 GB ≈ a few cents per hour while running; $0 when stopped
# Undo:          ./16_serve_test_task.sh stop ; aws ec2 delete-security-group --group-id <sg>
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account
CMD="${1:-status}"; shift || true
MV="${AQUA_PREDICTOR_VERSION:-mlp_ds1_202610090559}"
while [[ $# -gt 0 ]]; do case "$1" in --version) MV="$2"; shift 2;; *) die "unknown arg $1";; esac; done

ensure_test_sg() {
  local vpc id ip
  vpc="$(default_vpc_id)"
  id="$(aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$vpc" "Name=group-name,Values=$SG_TEST_NAME" \
        --query 'SecurityGroups[0].GroupId' --output text)"
  if [[ "$id" == "None" ]]; then
    id="$(aws ec2 create-security-group --group-name "$SG_TEST_NAME" --description "aquaagent test task: operator IP only" \
          --vpc-id "$vpc" --tag-specifications "ResourceType=security-group,Tags=[{$TAG_CLI}]" --query GroupId --output text)"
  fi
  ip="$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')"
  for port in 8080 8001; do
    aws ec2 authorize-security-group-ingress --group-id "$id" --protocol tcp --port "$port" --cidr "${ip}/32" >/dev/null 2>&1 || true
  done
  log "test SG $id allows 8080/8001 from ${ip}/32 only" >&2
  printf '%s' "$id"
}

task_ip() {
  local eni
  eni="$(aws ecs describe-tasks --cluster "$ECS_CLUSTER" --tasks "$1" \
        --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value | [0]" --output text)"
  aws ec2 describe-network-interfaces --network-interface-ids "$eni" --query 'NetworkInterfaces[0].Association.PublicIp' --output text
}

case "$CMD" in
  start)
    [[ -z "$(state_get test_task_arn)" ]] || die "a test task is already recorded — run '$0 stop' first"
    export IMAGE_TAG; IMAGE_TAG="$(state_need image_tag)"
    for repo in "$ECR_REPO_SIM" "$ECR_REPO_API" "$ECR_REPO_PREDICTOR"; do
      aws ecr describe-images --repository-name "$repo" --image-ids "imageTag=$IMAGE_TAG" >/dev/null 2>&1 \
        || die "image $repo:$IMAGE_TAG missing — run 05_build_push_images.sh"
    done
    aws s3api head-object --bucket "$AQUA_BUCKET" --key "models/predictor/$MV/model.tar.gz" >/dev/null \
      || die "s3://$AQUA_BUCKET/models/predictor/$MV/model.tar.gz missing — run python -m ml.predictor.package --upload"
    SG_ID="$(ensure_test_sg)"
    export AQUA_PREDICTOR_VERSION="$MV"
    TD_FILE="$(mktemp)"; render "$INFRA_DIR/ecs/serve-test-task-definition.json.tpl" > "$TD_FILE"
    TD_ARN="$(aws ecs register-task-definition --cli-input-json "file://$TD_FILE" --query 'taskDefinition.taskDefinitionArn' --output text)"
    ok "registered $TD_ARN"
    API_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
    state_put test_api_key "$API_KEY"
    SUBNETS="$(default_subnets_csv)"
    OVR="$(python3 -c 'import json,sys; print(json.dumps({"containerOverrides":[{"name":"api","environment":[{"name":"AQUA_API_KEY","value":sys.argv[1]}]}]}))' "$API_KEY")"
    TASK_ARN="$(aws ecs run-task --cluster "$ECS_CLUSTER" --task-definition "$TD_ARN" --count 1 \
      --capacity-provider-strategy capacityProvider=FARGATE_SPOT,weight=1 \
      --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
      --overrides "$OVR" --tags "key=$PROJECT_TAG_KEY,value=$PROJECT_TAG_VALUE" "key=purpose,value=test" \
      --query 'tasks[0].taskArn' --output text)"
    [[ "$TASK_ARN" == arn:* ]] || die "run-task failed: $TASK_ARN"
    state_put test_task_arn "$TASK_ARN"
    log "waiting for RUNNING (image pulls + model download, ~1–3 min)…"
    aws ecs wait tasks-running --cluster "$ECS_CLUSTER" --tasks "$TASK_ARN" \
      || die "task did not reach RUNNING — aws ecs describe-tasks --cluster $ECS_CLUSTER --tasks $TASK_ARN --query 'tasks[0].[stoppedReason,containers[].reason]'"
    IP="$(task_ip "$TASK_ARN")"; state_put test_task_ip "$IP"
    ok "test task RUNNING at $IP — predictor :8001, api :8080 (X-Api-Key in infra/.state/test_api_key). Next: $0 smoke ; then $0 stop"
    ;;
  smoke)
    IP="$(state_need test_task_ip)"; KEY="$(state_need test_api_key)"
    for i in $(seq 1 40); do curl -fsS -m 4 "http://$IP:8001/predictor/health" >/dev/null 2>&1 && break; sleep 3; done
    curl -fsS -m 5 "http://$IP:8001/predictor/health" && echo
    curl -sS -m 5 -H "X-Api-Key: $KEY" "http://$IP:8080/api/health" && echo
    cd "$REPO_ROOT" && "$REPO_ROOT/.venv/bin/python" -m ml.serve.smoke --url "http://$IP:8001" \
      --artifact "s3://$AQUA_BUCKET/models/predictor/$MV/model.tar.gz" --n 50 \
      --record "data/experiments/$MV/ecs_test_smoke.json" && ok "predictor smoke passed (parity ≤ 1e-5, firewall 422)"
    ;;
  status)
    TASK_ARN="$(state_get test_task_arn)"; [[ -n "$TASK_ARN" ]] || { log "no test task recorded"; exit 0; }
    aws ecs describe-tasks --cluster "$ECS_CLUSTER" --tasks "$TASK_ARN" \
      --query 'tasks[0].{status:lastStatus,health:healthStatus,containers:containers[].[name,lastStatus,healthStatus]}' --output json
    ;;
  stop)
    TASK_ARN="$(state_get test_task_arn)"; [[ -n "$TASK_ARN" ]] || { log "no test task recorded"; exit 0; }
    aws ecs stop-task --cluster "$ECS_CLUSTER" --task "$TASK_ARN" --reason "test done" >/dev/null || true
    aws ecs wait tasks-stopped --cluster "$ECS_CLUSTER" --tasks "$TASK_ARN" || true
    rm -f "$STATE_DIR/test_task_arn" "$STATE_DIR/test_task_ip" "$STATE_DIR/test_api_key"
    ok "test task stopped (no compute billing). SG $SG_TEST_NAME kept (free)."
    ;;
  *) die "usage: $0 start|smoke|status|stop" ;;
esac
