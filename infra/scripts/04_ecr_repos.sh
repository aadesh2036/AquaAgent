#!/usr/bin/env bash
# =============================================================================
# 04_ecr_repos.sh — ECR repositories for the three images (sim, api, predictor — BI-26)
# BACKBONE:      §3.2 (images: aquaagent-sim, aquaagent-api; tag = git short SHA)
# Prerequisites: 00 passes
# Creates:       ECR repos $ECR_REPO_SIM, $ECR_REPO_API, $ECR_REPO_PREDICTOR (scan-on-push, tagged, keep-last-15 lifecycle)
# Verify:        aws ecr describe-repositories --repository-names aquaagent-sim aquaagent-api
# Undo:          99_teardown.sh (delete-repository --force)
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account

LIFECYCLE='{"rules":[{"rulePriority":1,"description":"keep last 15","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":15},"action":{"type":"expire"}}]}'

for repo in "$ECR_REPO_SIM" "$ECR_REPO_API" "$ECR_REPO_PREDICTOR"; do
  if aws ecr describe-repositories --repository-names "$repo" >/dev/null 2>&1; then
    ok "repo $repo exists"
  else
    aws ecr create-repository --repository-name "$repo" \
      --image-scanning-configuration scanOnPush=true --tags "$TAG_CLI" >/dev/null
    ok "repo $repo created"
  fi
  aws ecr put-image-scanning-configuration --repository-name "$repo" --image-scanning-configuration scanOnPush=true >/dev/null
  aws ecr put-lifecycle-policy --repository-name "$repo" --lifecycle-policy-text "$LIFECYCLE" >/dev/null
done
aws ecr describe-repositories --repository-names "$ECR_REPO_SIM" "$ECR_REPO_API" "$ECR_REPO_PREDICTOR" \
  --query 'repositories[].repositoryUri' --output table
