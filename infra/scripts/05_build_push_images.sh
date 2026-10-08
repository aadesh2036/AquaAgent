#!/usr/bin/env bash
# =============================================================================
# 05_build_push_images.sh — build + push aquaagent-sim and aquaagent-api, tag = git short SHA
# BACKBONE:      §3.2 (ECR, tag = git short SHA)
# Prerequisites: 04 done; clean git tree recommended (tag must identify the code)
# Creates:       images <repo>:<sha> in both ECR repos; state file image_tag
# Verify:        aws ecr describe-images --repository-name aquaagent-api --image-ids imageTag=$(git rev-parse --short HEAD)
# Undo:          aws ecr batch-delete-image --repository-name <repo> --image-ids imageTag=<sha>
# Docker check:  if `docker info` fails (e.g. CloudShell), falls back to codebuild_image.sh.
#                Force with:  ./05_build_push_images.sh --codebuild
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account

IMAGE_TAG="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
[[ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]] && warn "working tree is dirty — tag $IMAGE_TAG will not exactly match the code"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
export IMAGE_TAG

if [[ "${1:-}" == "--codebuild" ]] || ! docker info >/dev/null 2>&1; then
  warn "docker unavailable or --codebuild given → using CodeBuild fallback"
  bash "$(dirname "$0")/codebuild_image.sh"
else
  aws ecr get-login-password | docker login --username AWS --password-stdin "$REGISTRY"
  ( cd "$REPO_ROOT"
    docker build -f sim/Dockerfile -t "$REGISTRY/$ECR_REPO_SIM:$IMAGE_TAG" .
    docker build -f api/Dockerfile -t "$REGISTRY/$ECR_REPO_API:$IMAGE_TAG" .
    docker push "$REGISTRY/$ECR_REPO_SIM:$IMAGE_TAG"
    docker push "$REGISTRY/$ECR_REPO_API:$IMAGE_TAG" )
fi
state_put image_tag "$IMAGE_TAG"
ok "images pushed with tag $IMAGE_TAG"
