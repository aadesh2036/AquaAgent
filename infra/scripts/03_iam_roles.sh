#!/usr/bin/env bash
# =============================================================================
# 03_iam_roles.sh — create the per-actor IAM roles from infra/iam/*.json
# BACKBONE:      §10.3 (least privilege, one role per actor); BACKBONE_ISSUES BI-05, BI-10
# Prerequisites: 02 done (policies reference the bucket name)
# Creates:       roles aqua-ecs-exec, aqua-sim-task, aqua-api-task, aqua-sagemaker-exec
#                (+ aqua-codebuild with --with-codebuild), each with inline policy "<role>-inline"
# Verify:        aws iam get-role --role-name aqua-api-task
#                aws iam get-role-policy --role-name aqua-api-task --policy-name aqua-api-task-inline
# Undo:          99_teardown.sh (deletes inline policies, detaches managed, deletes roles)
# Re-run after 14_bedrock_check.sh to narrow Bedrock permissions to the discovered model.
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account
IAM_DIR="$INFRA_DIR/iam"
WITH_CODEBUILD=0; [[ "${1:-}" == "--with-codebuild" ]] && WITH_CODEBUILD=1

# Bedrock resources (BI-05). Narrow to the discovered model once 14 has run.
BEDROCK_ARNS="$(state_get bedrock_resource_arns_json)"
if [[ -z "$BEDROCK_ARNS" ]]; then
  BEDROCK_ARNS="[\"arn:aws:bedrock:*::foundation-model/anthropic.*\",\"arn:aws:bedrock:${AWS_REGION}:${ACCOUNT_ID}:inference-profile/*\"]"
  warn "Bedrock permissions use the broad Anthropic wildcard until 14_bedrock_check.sh runs (then re-run 03)"
fi
export BEDROCK_RESOURCE_ARNS_JSON="$BEDROCK_ARNS"

ensure_role() {  # name trust_file
  local name="$1" trust="$2"
  if aws iam get-role --role-name "$name" >/dev/null 2>&1; then
    aws iam update-assume-role-policy --role-name "$name" --policy-document "file://$trust"
    ok "role $name exists (trust policy refreshed)"
  else
    aws iam create-role --role-name "$name" --assume-role-policy-document "file://$trust" \
      --tags "$TAG_CLI" --description "AquaAgent $name (BACKBONE §10.3)" >/dev/null
    ok "role $name created"
  fi
}

put_inline() {  # name template
  local name="$1" tpl="$2" rendered
  rendered="$(mktemp)"; render "$tpl" > "$rendered"
  aws iam put-role-policy --role-name "$name" --policy-name "${name}-inline" --policy-document "file://$rendered"
  rm -f "$rendered"
  ok "inline policy ${name}-inline applied"
}

ensure_role "$ROLE_ECS_EXEC" "$IAM_DIR/trust-ecs-tasks.json"
aws iam attach-role-policy --role-name "$ROLE_ECS_EXEC" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
put_inline "$ROLE_ECS_EXEC" "$IAM_DIR/aqua-ecs-exec.policy.json.tpl"

ensure_role "$ROLE_SIM_TASK" "$IAM_DIR/trust-ecs-tasks.json"
put_inline "$ROLE_SIM_TASK" "$IAM_DIR/aqua-sim-task.policy.json.tpl"

ensure_role "$ROLE_API_TASK" "$IAM_DIR/trust-ecs-tasks.json"
put_inline "$ROLE_API_TASK" "$IAM_DIR/aqua-api-task.policy.json.tpl"

ensure_role "$ROLE_SAGEMAKER_EXEC" "$IAM_DIR/trust-sagemaker.json"
put_inline "$ROLE_SAGEMAKER_EXEC" "$IAM_DIR/aqua-sagemaker-exec.policy.json.tpl"
state_put sagemaker_role_arn "arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_SAGEMAKER_EXEC}"

if [[ $WITH_CODEBUILD -eq 1 ]]; then
  ensure_role "$ROLE_CODEBUILD" "$IAM_DIR/trust-codebuild.json"
  put_inline "$ROLE_CODEBUILD" "$IAM_DIR/aqua-codebuild.policy.json.tpl"
fi

log "IAM is eventually consistent — wait ~10 s before using new roles."
ok "IAM roles ready"
