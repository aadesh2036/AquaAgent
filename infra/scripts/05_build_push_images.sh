#!/usr/bin/env bash
# =============================================================================
# 05_build_push_images.sh — build + push aquaagent-sim, aquaagent-api, aquaagent-predictor; tag = git short SHA
# BACKBONE:      §3.2 (ECR, tag = git short SHA)
# Prerequisites: 04 done; clean git tree recommended (tag must identify the code)
# Creates:       images <repo>:<tag> in the ECR repos; state file image_tag
# Usage:         ./05_build_push_images.sh [--only=sim|api|predictor] [--codebuild]
#                IMAGE_TAG=<tag> overrides the git SHA (use when the tree is dirty, e.g. dev-<yyyymmddhhmm>)
# Verify:        aws ecr describe-images --repository-name aquaagent-api --image-ids imageTag=$(git rev-parse --short HEAD)
# Undo:          aws ecr batch-delete-image --repository-name <repo> --image-ids imageTag=<sha>
# Docker check:  if `docker info` fails (e.g. CloudShell), falls back to codebuild_image.sh.
#                Force with:  ./05_build_push_images.sh --codebuild
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account

ONLY=""; for a in "$@"; do case "$a" in --only=*) ONLY="${a#--only=}";; esac; done   # --only=sim builds just aquaagent-sim
IMAGE_TAG="${IMAGE_TAG:-$(git -C "$REPO_ROOT" rev-parse --short HEAD)}"
want() { [[ -z "$ONLY" || "$ONLY" == "$1" ]]; }
[[ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]] && warn "working tree is dirty — tag $IMAGE_TAG will not exactly match the code"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
export IMAGE_TAG

if [[ " $* " == *" --codebuild "* ]] || ! docker info >/dev/null 2>&1; then
  warn "docker unavailable or --codebuild given → using CodeBuild fallback"
  bash "$(dirname "$0")/codebuild_image.sh"
else
  aws ecr get-login-password | docker login --username AWS --password-stdin "$REGISTRY"
  ( cd "$REPO_ROOT"
    if want sim; then
      docker build --format docker -f sim/Dockerfile -t "$REGISTRY/$ECR_REPO_SIM:$IMAGE_TAG" . 2>/dev/null \
        || docker build -f sim/Dockerfile -t "$REGISTRY/$ECR_REPO_SIM:$IMAGE_TAG" .
      docker push "$REGISTRY/$ECR_REPO_SIM:$IMAGE_TAG"
    fi
    if want api; then
      docker build -f api/Dockerfile -t "$REGISTRY/$ECR_REPO_API:$IMAGE_TAG" .
      docker push "$REGISTRY/$ECR_REPO_API:$IMAGE_TAG"
    fi
    if want predictor; then
      docker build --format docker -f ml/serve/Dockerfile -t "$REGISTRY/$ECR_REPO_PREDICTOR:$IMAGE_TAG" . 2>/dev/null \
        || docker build -f ml/serve/Dockerfile -t "$REGISTRY/$ECR_REPO_PREDICTOR:$IMAGE_TAG" .
      docker push "$REGISTRY/$ECR_REPO_PREDICTOR:$IMAGE_TAG"
    fi )
fi
state_put image_tag "$IMAGE_TAG"
ok "images pushed with tag $IMAGE_TAG"
