#!/usr/bin/env bash
# =============================================================================
# codebuild_image.sh — build/push images with AWS CodeBuild when local docker is unavailable
# BACKBONE:      §3.2; master-prompt CloudShell fallback; BACKBONE_ISSUES BI-10 (aqua-codebuild role)
# Prerequisites: 02, 04 done; `03_iam_roles.sh --with-codebuild` done; CODEBUILD_IMAGE set (<VERIFY>)
# Creates:       CodeBuild project $CODEBUILD_PROJECT; s3://$AQUA_BUCKET/codebuild/source.zip
# Verify:        aws codebuild list-builds-for-project --project-name "$CODEBUILD_PROJECT"
# Undo:          aws codebuild delete-project --name "$CODEBUILD_PROJECT"  (99_teardown.sh does this)
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account; require_var CODEBUILD_IMAGE; require_cmd zip
IMAGE_TAG="${IMAGE_TAG:-$(git -C "$REPO_ROOT" rev-parse --short HEAD)}"

aws iam get-role --role-name "$ROLE_CODEBUILD" >/dev/null 2>&1 || die "role $ROLE_CODEBUILD missing — run 03_iam_roles.sh --with-codebuild"

SRC_ZIP="$(mktemp -d)/source.zip"
( cd "$REPO_ROOT" && git archive --format=zip -o "$SRC_ZIP" HEAD )
( cd "$REPO_ROOT" && zip -q "$SRC_ZIP" infra/codebuild/buildspec.yml )
aws s3 cp "$SRC_ZIP" "s3://$AQUA_BUCKET/codebuild/source.zip"

if ! aws codebuild batch-get-projects --names "$CODEBUILD_PROJECT" --query 'projects[0].name' --output text | grep -q "$CODEBUILD_PROJECT"; then
  aws codebuild create-project --name "$CODEBUILD_PROJECT" \
    --source "type=S3,location=$AQUA_BUCKET/codebuild/source.zip,buildspec=infra/codebuild/buildspec.yml" \
    --artifacts type=NO_ARTIFACTS \
    --environment "type=LINUX_CONTAINER,image=$CODEBUILD_IMAGE,computeType=BUILD_GENERAL1_SMALL,privilegedMode=true" \
    --service-role "arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_CODEBUILD}" \
    --tags "key=${PROJECT_TAG_KEY},value=${PROJECT_TAG_VALUE}" >/dev/null
  ok "CodeBuild project created"
fi

BUILD_ID="$(aws codebuild start-build --project-name "$CODEBUILD_PROJECT" \
  --environment-variables-override \
    "name=AWS_REGION,value=$AWS_REGION" "name=ACCOUNT_ID,value=$ACCOUNT_ID" \
    "name=ECR_REPO_SIM,value=$ECR_REPO_SIM" "name=ECR_REPO_API,value=$ECR_REPO_API" \
    "name=IMAGE_TAG,value=$IMAGE_TAG" \
  --query 'build.id' --output text)"
log "build $BUILD_ID started — polling every 15 s"
while :; do
  STATUS="$(aws codebuild batch-get-builds --ids "$BUILD_ID" --query 'builds[0].buildStatus' --output text)"
  [[ "$STATUS" == "IN_PROGRESS" ]] || break
  sleep 15
done
[[ "$STATUS" == "SUCCEEDED" ]] || die "CodeBuild $STATUS — logs: aws logs tail /aws/codebuild/$CODEBUILD_PROJECT --since 30m"
ok "CodeBuild pushed images with tag $IMAGE_TAG"
