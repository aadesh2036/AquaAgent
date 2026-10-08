#!/usr/bin/env bash
# =============================================================================
# 07_run_datagen.sh — generate ds1 on ECS: N parallel `generate` shards, then one `merge` task
# BACKBONE:      §8.6 (batch execution), §10.2 raw/ processed/, G2
# Prerequisites: 02,03,04,05,06 done; module 02 implemented (sim image supports generate/merge)
# Creates:       task definition family $TASKDEF_FAMILY_DATAGEN (new revision per run); N+1 ECS tasks
#                s3://$AQUA_BUCKET/raw/ds1/shard=i/…  and  processed/ds1/ + manifest.json
# Verify:        aws s3 ls "s3://$AQUA_BUCKET/processed/ds1/manifest.json"
# Undo:          aws s3 rm "s3://$AQUA_BUCKET/raw/ds1/" --recursive  (data); task defs deregistered by 99
# Network:       default VPC, default security group (egress only), public IP for ECR/S3 access
# Usage:         ./07_run_datagen.sh [NUM_SHARDS]   (default $DATAGEN_NUM_SHARDS)
# CUT LINE (BACKBONE §13, end of Day 2): if this fails, run `make datagen-local` and upload with
#                aws s3 sync data/raw/ds1 s3://$AQUA_BUCKET/raw/ds1 — ECS RunTask becomes a slide.
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account
N="${1:-$DATAGEN_NUM_SHARDS}"
DS="$AQUA_DATASET_VERSION"
export IMAGE_TAG; IMAGE_TAG="$(state_need image_tag)"

TD_FILE="$(mktemp)"; render "$INFRA_DIR/ecs/datagen-task-definition.json.tpl" > "$TD_FILE"
TD_ARN="$(aws ecs register-task-definition --cli-input-json "file://$TD_FILE" --query 'taskDefinition.taskDefinitionArn' --output text)"
ok "registered $TD_ARN"

SUBNETS="$(default_subnets_csv)"
DEFAULT_SG="$(aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$(default_vpc_id)" Name=group-name,Values=default --query 'SecurityGroups[0].GroupId' --output text)"
NETCFG="awsvpcConfiguration={subnets=[${SUBNETS}],securityGroups=[${DEFAULT_SG}],assignPublicIp=ENABLED}"

GIT_SHA="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
run_task() {  # json-command-array  → prints task arn. Fargate Spot first (~70% cheaper), on-demand fallback.
  local ov="{\"containerOverrides\":[{\"name\":\"sim\",\"command\":$1,\"environment\":[{\"name\":\"GIT_SHA\",\"value\":\"$GIT_SHA\"}]}]}"
  local arn
  for cp in FARGATE_SPOT FARGATE; do
    arn="$(aws ecs run-task --cluster "$ECS_CLUSTER" --capacity-provider-strategy "capacityProvider=$cp,weight=1" \
      --task-definition "$TD_ARN" --network-configuration "$NETCFG" --tags "$TAG_CLI_LOWER" \
      --overrides "$ov" --query 'tasks[0].taskArn' --output text 2>/dev/null || true)"
    [[ -n "$arn" && "$arn" != "None" ]] && { [[ $cp == FARGATE ]] && warn "Spot unavailable — used on-demand Fargate" >&2; printf '%s' "$arn"; return 0; }
  done
  die "run-task failed on both FARGATE_SPOT and FARGATE"
}

wait_and_check() {  # task arns...
  local arns=("$@")
  log "waiting for ${#arns[@]} task(s) to stop (waiter retries until done)"
  local tries=0
  until aws ecs wait tasks-stopped --cluster "$ECS_CLUSTER" --tasks "${arns[@]}" 2>/dev/null; do
    tries=$((tries + 1)); [[ $tries -lt 12 ]] || die "tasks still running after ~2 h — check the ECS console/logs"; log "still running…"
  done
  local bad
  bad="$(aws ecs describe-tasks --cluster "$ECS_CLUSTER" --tasks "${arns[@]}" \
    --query 'tasks[?containers[0].exitCode!=`0`].[taskArn,containers[0].exitCode,stoppedReason]' --output text)"
  [[ -z "$bad" ]] || die "failed tasks:\n$bad\nlogs: aws logs tail $LOG_GROUP_DATAGEN --since 1h"
}

ARNS=()
for ((i = 0; i < N; i++)); do
  CMD="[\"generate\",\"--config\",\"config/generation/${DS}.yaml\",\"--shard\",\"$i\",\"--num-shards\",\"$N\",\"--out\",\"s3://${AQUA_BUCKET}/raw/${DS}/shard=$i/\"]"
  ARNS+=("$(run_task "$CMD")")
  log "shard $i → ${ARNS[-1]##*/}"
done
wait_and_check "${ARNS[@]}"
ok "all $N generate shards finished"

MERGE_CMD="[\"merge\",\"--config\",\"config/generation/${DS}.yaml\",\"--raw\",\"s3://${AQUA_BUCKET}/raw/${DS}/\",\"--out\",\"s3://${AQUA_BUCKET}/processed/${DS}/\"]"
MERGE_ARN="$(run_task "$MERGE_CMD")"
wait_and_check "$MERGE_ARN"

aws s3 ls "s3://$AQUA_BUCKET/raw/$DS/" --recursive --summarize | tail -n 2
aws s3 ls "s3://$AQUA_BUCKET/processed/$DS/"
aws s3 cp "s3://$AQUA_BUCKET/processed/$DS/manifest.json" - | head -c 1500; echo
ok "ds $DS generated and merged"
