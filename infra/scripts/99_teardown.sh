#!/usr/bin/env bash
# =============================================================================
# 99_teardown.sh — ordered deletion of every AquaAgent resource
# BACKBONE:      §10.5 (delete endpoint after judging; keep model.tar.gz), §10
# Prerequisites: infra/env.sh. Asks for confirmation (type the bucket name).
# Deletes (in order): SageMaker endpoint → endpoint configs → models; ECS service; task definitions;
#                API Gateway; ALB listener → ALB → target group; security groups; ECS cluster; log groups;
#                ECR repos; SSM params; Amplify app; CodeBuild project; IAM roles; budget.
# KEEPS:         S3 bucket (data, model.tar.gz, experiments) unless --purge.
# Usage:         ./99_teardown.sh [--purge] [--endpoint-only]
#                --endpoint-only : just stop the most expensive idle item (the endpoint) — do this right after judging
# Verify:        ./90_status.sh shows "-" everywhere
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account
PURGE=0; ENDPOINT_ONLY=0
for a in "$@"; do case "$a" in --purge) PURGE=1;; --endpoint-only) ENDPOINT_ONLY=1;; esac; done
try() { "$@" >/dev/null 2>&1 && ok "$*" || log "skip (absent): ${*:1:3}"; }

echo "This deletes AquaAgent AWS resources in $AWS_REGION (account $ACCOUNT_ID)."
[[ $PURGE -eq 1 ]] && echo "!! --purge: the S3 bucket and ALL versions of ALL data will be deleted !!"
confirm "Type the bucket name ($AQUA_BUCKET) to continue:" "$AQUA_BUCKET"

# 1. SageMaker (most expensive idle item)
try aws sagemaker delete-endpoint --endpoint-name "$AQUA_PREDICTOR_ENDPOINT"
for cfg in $(aws sagemaker list-endpoint-configs --name-contains aquaagent --query 'EndpointConfigs[].EndpointConfigName' --output text 2>/dev/null); do
  try aws sagemaker delete-endpoint-config --endpoint-config-name "$cfg"; done
[[ $ENDPOINT_ONLY -eq 1 ]] && { ok "endpoint-only teardown done"; exit 0; }
for m in $(aws sagemaker list-models --name-contains aquaagent --query 'Models[].ModelName' --output text 2>/dev/null); do
  try aws sagemaker delete-model --model-name "$m"; done

# 2. ECS service + task definitions
if aws ecs describe-services --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE" --query 'services[0].status' --output text 2>/dev/null | grep -q ACTIVE; then
  aws ecs update-service --cluster "$ECS_CLUSTER" --service "$ECS_SERVICE" --desired-count 0 >/dev/null
  try aws ecs delete-service --cluster "$ECS_CLUSTER" --service "$ECS_SERVICE" --force
  aws ecs wait services-inactive --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE" || true
fi
for fam in "$TASKDEF_FAMILY_SERVE" "$TASKDEF_FAMILY_DATAGEN"; do
  for td in $(aws ecs list-task-definitions --family-prefix "$fam" --query 'taskDefinitionArns[]' --output text 2>/dev/null); do
    try aws ecs deregister-task-definition --task-definition "$td"; done
done

# 3. API Gateway
API_ID="$(aws apigatewayv2 get-apis --query "Items[?Name=='$APIGW_NAME'].ApiId | [0]" --output text 2>/dev/null || true)"
[[ -n "$API_ID" && "$API_ID" != "None" ]] && try aws apigatewayv2 delete-api --api-id "$API_ID"

# 4. ALB → TG → SGs
ALB_ARN="$(aws elbv2 describe-load-balancers --names "$ALB_NAME" --query 'LoadBalancers[0].LoadBalancerArn' --output text 2>/dev/null || true)"
if [[ -n "$ALB_ARN" && "$ALB_ARN" != "None" ]]; then
  for l in $(aws elbv2 describe-listeners --load-balancer-arn "$ALB_ARN" --query 'Listeners[].ListenerArn' --output text); do
    try aws elbv2 delete-listener --listener-arn "$l"; done
  try aws elbv2 delete-load-balancer --load-balancer-arn "$ALB_ARN"
  aws elbv2 wait load-balancers-deleted --load-balancer-arns "$ALB_ARN" || true
fi
TG_ARN="$(aws elbv2 describe-target-groups --names "$TG_NAME" --query 'TargetGroups[0].TargetGroupArn' --output text 2>/dev/null || true)"
[[ -n "$TG_ARN" && "$TG_ARN" != "None" ]] && try aws elbv2 delete-target-group --target-group-arn "$TG_ARN"
VPC_ID="$(default_vpc_id)"
for sgname in "$SG_TASK_NAME" "$SG_ALB_NAME"; do
  SG="$(aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$VPC_ID" "Name=group-name,Values=$sgname" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)"
  [[ -n "$SG" && "$SG" != "None" ]] || continue
  for i in 1 2 3 4 5 6; do aws ec2 delete-security-group --group-id "$SG" 2>/dev/null && { ok "deleted SG $sgname"; break; }; log "SG $sgname busy (ENIs draining) — retry in 20 s"; sleep 20; done
done

# 5. ECS cluster + logs
try aws ecs delete-cluster --cluster "$ECS_CLUSTER"
for lg in "$LOG_GROUP_API" "$LOG_GROUP_SIM" "$LOG_GROUP_DATAGEN"; do try aws logs delete-log-group --log-group-name "$lg"; done

# 6. ECR, SSM, Amplify, CodeBuild
for repo in "$ECR_REPO_SIM" "$ECR_REPO_API"; do try aws ecr delete-repository --repository-name "$repo" --force; done
PARAMS="$(aws ssm get-parameters-by-path --path "$SSM_PREFIX" --query 'Parameters[].Name' --output text 2>/dev/null || true)"
# shellcheck disable=SC2086
[[ -n "$PARAMS" ]] && try aws ssm delete-parameters --names $PARAMS
APP_ID="$(aws amplify list-apps --query "apps[?name=='$AMPLIFY_APP_NAME'].appId | [0]" --output text 2>/dev/null || true)"
[[ -n "$APP_ID" && "$APP_ID" != "None" ]] && try aws amplify delete-app --app-id "$APP_ID"
try aws codebuild delete-project --name "$CODEBUILD_PROJECT"

# 7. IAM roles
for r in "$ROLE_ECS_EXEC" "$ROLE_SIM_TASK" "$ROLE_API_TASK" "$ROLE_SAGEMAKER_EXEC" "$ROLE_CODEBUILD"; do
  aws iam get-role --role-name "$r" >/dev/null 2>&1 || continue
  for p in $(aws iam list-role-policies --role-name "$r" --query 'PolicyNames[]' --output text); do
    aws iam delete-role-policy --role-name "$r" --policy-name "$p"; done
  for p in $(aws iam list-attached-role-policies --role-name "$r" --query 'AttachedPolicies[].PolicyArn' --output text); do
    aws iam detach-role-policy --role-name "$r" --policy-arn "$p"; done
  try aws iam delete-role --role-name "$r"
done

# 8. Budget (last, so it watches the teardown)
try aws budgets delete-budget --account-id "$ACCOUNT_ID" --budget-name "$BUDGET_NAME"

# 9. S3 (only with --purge): delete all versions + delete markers, then the bucket
if [[ $PURGE -eq 1 ]] && aws s3api head-bucket --bucket "$AQUA_BUCKET" 2>/dev/null; then
  for kind in Versions DeleteMarkers; do
    while :; do
      BATCH="$(aws s3api list-object-versions --bucket "$AQUA_BUCKET" --max-items 1000 \
        --query "{Objects: $kind[].{Key:Key,VersionId:VersionId}}" --output json)"
      echo "$BATCH" | grep -q '"Key"' || break
      aws s3api delete-objects --bucket "$AQUA_BUCKET" --delete "$BATCH" >/dev/null
    done
  done
  try aws s3api delete-bucket --bucket "$AQUA_BUCKET"
else
  log "S3 bucket kept: s3://$AQUA_BUCKET (use --purge to delete)"
fi
rm -f "$STATE_DIR"/{alb_arn,alb_dns,tg_arn,listener_arn,sg_alb_id,sg_task_id,api_id,api_url,amplify_app_id,amplify_origin}
ok "teardown complete — verify with ./90_status.sh"
