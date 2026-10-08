#!/usr/bin/env bash
# =============================================================================
# 90_status.sh — one-screen status of every AquaAgent resource (read-only)
# BACKBONE:      §10 (all resources), §10.5 (what is costing money)
# Prerequisites: infra/env.sh
# Creates:       nothing
# Verify/Undo:   n/a
# =============================================================================
source "$(dirname "$0")/lib.sh"
q() { "$@" 2>/dev/null || echo "-"; }
line() { printf '%-26s %s\n' "$1" "$2"; }

echo "================ AquaAgent status ($AWS_REGION, acct $ACCOUNT_ID) ================"
line "Budget"            "$(q aws budgets describe-budget --account-id "$ACCOUNT_ID" --budget-name "$BUDGET_NAME" --query 'Budget.[BudgetLimit.Amount,CalculatedSpend.ActualSpend.Amount]' --output text)"
line "S3 bucket"         "$(aws s3api head-bucket --bucket "$AQUA_BUCKET" 2>/dev/null && echo "s3://$AQUA_BUCKET" || echo "-")"
line "  ds manifest"     "$(q aws s3 ls "s3://$AQUA_BUCKET/processed/$AQUA_DATASET_VERSION/manifest.json" | awk '{print $1" "$2}')"
for r in "$ROLE_ECS_EXEC" "$ROLE_SIM_TASK" "$ROLE_API_TASK" "$ROLE_SAGEMAKER_EXEC" "$ROLE_CODEBUILD"; do
  line "IAM $r" "$(aws iam get-role --role-name "$r" >/dev/null 2>&1 && echo present || echo -)"
done
for repo in "$ECR_REPO_SIM" "$ECR_REPO_API"; do
  line "ECR $repo" "$(q aws ecr describe-images --repository-name "$repo" --query 'sort_by(imageDetails,&imagePushedAt)[-1].imageTags[0]' --output text)"
done
line "ECS cluster"       "$(q aws ecs describe-clusters --clusters "$ECS_CLUSTER" --query 'clusters[0].[status,runningTasksCount]' --output text)"
line "ECS service ($)"   "$(q aws ecs describe-services --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE" --query 'services[0].[status,desiredCount,runningCount]' --output text)"
line "ALB ($)"           "$(q aws elbv2 describe-load-balancers --names "$ALB_NAME" --query 'LoadBalancers[0].[State.Code,DNSName]' --output text)"
TG="$(state_get tg_arn)"; [[ -n "$TG" ]] && line "  targets" "$(q aws elbv2 describe-target-health --target-group-arn "$TG" --query 'TargetHealthDescriptions[].TargetHealth.State' --output text)"
line "API Gateway"       "$(state_get api_url)"
API_URL="$(state_get api_url)"; [[ -n "$API_URL" ]] && line "  /api/health" "$(curl -fsS -m 5 "$API_URL/api/health" 2>/dev/null || echo unreachable)"
line "SSM params"        "$(q aws ssm get-parameters-by-path --path "$SSM_PREFIX" --query 'length(Parameters)' --output text)"
line "SageMaker endpoint (\$)" "$(q aws sagemaker describe-endpoint --endpoint-name "$AQUA_PREDICTOR_ENDPOINT" --query EndpointStatus --output text)"
line "Last training job" "$(q aws sagemaker list-training-jobs --name-contains aquaagent --sort-by CreationTime --sort-order Descending --max-results 1 --query 'TrainingJobSummaries[0].[TrainingJobName,TrainingJobStatus]' --output text)"
line "Bedrock model id"  "$(state_get bedrock_model_id)"
line "Amplify"           "$(state_get amplify_origin)"
line "CodeBuild project" "$(q aws codebuild batch-get-projects --names "$CODEBUILD_PROJECT" --query 'projects[0].name' --output text)"
echo "($) = bills while idle — see docs/aws/04_TEARDOWN_AND_COST.md"
