#!/usr/bin/env bash
# =============================================================================
# 14_bedrock_check.sh — region/model-access check (D1/D2) + minimal Converse call
# BACKBONE:      §10.1 (D1 region), §15 D2 (model), §9.6; BACKBONE_ISSUES BI-05 (inference profiles)
# Prerequisites: 00 passes. MANUAL STEP may be needed first (see box below).
# Creates:       nothing in AWS; writes infra/.state/bedrock_model_id and bedrock_resource_arns_json
# Verify:        the final "OK" line printed by the Converse smoke call
# Undo:          n/a
# Primer:        docs/aws/02_BEDROCK_PRIMER.md
#
# ┌──────────────────────────────── MANUAL STEP ────────────────────────────────┐
# │ If the Converse call fails with AccessDeniedException mentioning model access │
# │ open the Bedrock console in $AWS_REGION → "Model access" and request/enable  │
# │ the Anthropic Claude model you intend to use (some accounts also need a      │
# │ one-time use-case form). Then re-run this script.                            │
# └──────────────────────────────────────────────────────────────────────────────┘
# Usage: ./14_bedrock_check.sh                    → list candidates, then exit asking you to choose
#        AQUA_BEDROCK_MODEL_ID=<id> ./14_bedrock_check.sh   → verify that id end-to-end
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account

log "Anthropic foundation models in $AWS_REGION (id | inference types | lifecycle):"
aws bedrock list-foundation-models --by-provider anthropic \
  --query 'modelSummaries[].[modelId, join(`,`, inferenceTypesSupported), modelLifecycle.status]' --output table

log "Inference profiles visible to this account (use these ids if the model shows only INFERENCE_PROFILE):"
aws bedrock list-inference-profiles --query 'inferenceProfileSummaries[?contains(inferenceProfileId, `anthropic`)].[inferenceProfileId,status]' --output table || warn "list-inference-profiles not available in this CLI/region"

MODEL_ID="${AQUA_BEDROCK_MODEL_ID:-$(state_get bedrock_model_id)}"
if [[ -z "$MODEL_ID" ]]; then
  warn "Choose one id from the tables above (a current Claude model, BACKBONE D2), then re-run:"
  warn "  AQUA_BEDROCK_MODEL_ID=<id> $0"
  exit 3
fi

log "Converse smoke call with $MODEL_ID"
RESP="$(aws bedrock-runtime converse --model-id "$MODEL_ID" \
  --messages '[{"role":"user","content":[{"text":"Reply with exactly: OK"}]}]' \
  --inference-config '{"maxTokens":10,"temperature":0}' \
  --query 'output.message.content[0].text' --output text)" \
  || die "Converse failed — see MANUAL STEP box (model access), region (D1), or use an inference-profile id (BI-05)"
log "model replied: $RESP"

# Record discovered id + IAM resource ARNs (BI-05) for 03 (re-run) and 11.
state_put bedrock_model_id "$MODEL_ID"
if [[ "$MODEL_ID" == arn:* ]]; then
  ARNS="[\"$MODEL_ID\",\"arn:aws:bedrock:*::foundation-model/*\"]"
elif aws bedrock get-inference-profile --inference-profile-identifier "$MODEL_ID" >/dev/null 2>&1; then
  ARNS="$(aws bedrock get-inference-profile --inference-profile-identifier "$MODEL_ID" \
    --query '[inferenceProfileArn, models[].modelArn][]' --output json | tr -d '\n ')"
else
  ARNS="[\"arn:aws:bedrock:${AWS_REGION}::foundation-model/${MODEL_ID}\"]"
fi
state_put bedrock_resource_arns_json "$ARNS"
ok "Bedrock reachable. Saved model id + IAM ARNs. Next: re-run 03_iam_roles.sh (narrow perms) and 11_ssm_params.sh"

if python3 -c "import boto3" 2>/dev/null; then
  ( cd "$REPO_ROOT" && AQUA_BEDROCK_MODEL_ID="$MODEL_ID" AQUA_REGION="$AWS_REGION" python3 -m api.agent.smoke_bedrock ) \
    && ok "python Converse+toolConfig smoke passed" \
    || warn "api/agent/smoke_bedrock.py not implemented yet (module 07) — CLI check above is sufficient for D1/D2"
fi
