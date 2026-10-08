#!/usr/bin/env bash
# =============================================================================
# 02_s3_bucket.sh — data/model bucket with versioning, public access blocked, prefix layout
# BACKBONE:      §10.2 (layout), §3.2
# Prerequisites: 00 passes
# Creates:       s3://$AQUA_BUCKET (versioned, SSE-S3, public access blocked, tagged)
#                prefix placeholders: configs/ raw/ processed/ features/ models/ experiments/ demo/
#                uploads config/sensors/*.json, config/generation/*.yaml, config/networks/*.json → configs/
# Verify:        aws s3 ls "s3://$AQUA_BUCKET/"
#                aws s3api get-bucket-versioning --bucket "$AQUA_BUCKET"
# Undo:          99_teardown.sh --purge  (bucket is KEPT by default teardown)
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account

if aws s3api head-bucket --bucket "$AQUA_BUCKET" 2>/dev/null; then
  ok "bucket $AQUA_BUCKET exists"
else
  log "creating bucket $AQUA_BUCKET"
  if [[ "$AWS_REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$AQUA_BUCKET"
  else
    aws s3api create-bucket --bucket "$AQUA_BUCKET" --create-bucket-configuration "LocationConstraint=$AWS_REGION"
  fi
fi

aws s3api put-public-access-block --bucket "$AQUA_BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-versioning --bucket "$AQUA_BUCKET" --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket "$AQUA_BUCKET" --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-bucket-tagging --bucket "$AQUA_BUCKET" \
  --tagging "TagSet=[{Key=${PROJECT_TAG_KEY},Value=${PROJECT_TAG_VALUE}}]"

for prefix in configs raw processed features models experiments demo; do
  aws s3api put-object --bucket "$AQUA_BUCKET" --key "$prefix/" >/dev/null
done

# Configs (BACKBONE §10.2 configs/): networks, generation, sensors
aws s3 cp "$REPO_ROOT/config/sensors/"    "s3://$AQUA_BUCKET/configs/sensors/"    --recursive --exclude "*" --include "*.json"
aws s3 cp "$REPO_ROOT/config/generation/" "s3://$AQUA_BUCKET/configs/generation/" --recursive --exclude "*" --include "*.yaml"
aws s3 cp "$REPO_ROOT/config/networks/"   "s3://$AQUA_BUCKET/configs/networks/"   --recursive --exclude "*" --include "*.json" --include "*.inp"

state_put bucket "$AQUA_BUCKET"
aws s3 ls "s3://$AQUA_BUCKET/"
ok "bucket ready: s3://$AQUA_BUCKET"
