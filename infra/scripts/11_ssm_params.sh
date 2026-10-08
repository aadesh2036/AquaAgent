#!/usr/bin/env bash
# =============================================================================
# 11_ssm_params.sh — runtime config + API key in SSM Parameter Store (/aquaagent/*)
# BACKBONE:      §10.3 (secrets in SSM → ECS env), §10.4 (canonical env names), D8
# Prerequisites: 00 passes. RUN BEFORE 09 (task definition references these parameters).
# Creates:       /aquaagent/AQUA_API_KEY (SecureString, generated once; --rotate to regenerate)
#                /aquaagent/{AQUA_AGENT,AQUA_BEDROCK_MODEL_ID,AQUA_PREDICTOR_VERSION,
#                            AQUA_THRESHOLDS_URI,AQUA_SIGNATURES_URI,AQUA_CORS_ORIGINS} (String)
# Verify:        aws ssm get-parameters-by-path --path /aquaagent --query 'Parameters[].Name'
# Undo:          99_teardown.sh (delete-parameters)
# Note:          values that are not known yet are written as "unset" and re-written on re-run.
#                After changing values: ./09_ecs_service.sh  (forces a new deployment).
#                The API key will also be put in the Amplify build env — it is a deterrent, not a secret (BI-13).
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account
ROTATE=0; [[ "${1:-}" == "--rotate" ]] && ROTATE=1

put_param() {  # name value type
  aws ssm put-parameter --name "${SSM_PREFIX}/$1" --value "$2" --type "$3" --overwrite >/dev/null
  aws ssm add-tags-to-resource --resource-type Parameter --resource-id "${SSM_PREFIX}/$1" --tags "$TAG_CLI" >/dev/null
  ok "${SSM_PREFIX}/$1 ($3)"
}
val_or_unset() { [[ -n "${1:-}" ]] && printf '%s' "$1" || printf 'unset'; }

if [[ $ROTATE -eq 1 ]] || ! aws ssm get-parameter --name "${SSM_PREFIX}/AQUA_API_KEY" >/dev/null 2>&1; then
  KEY="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"
  put_param AQUA_API_KEY "$KEY" SecureString
  log "API key generated (read it with: aws ssm get-parameter --name ${SSM_PREFIX}/AQUA_API_KEY --with-decryption --query Parameter.Value --output text)"
else
  ok "${SSM_PREFIX}/AQUA_API_KEY exists (use --rotate to regenerate)"
fi

MODEL_ID="${AQUA_BEDROCK_MODEL_ID:-$(state_get bedrock_model_id)}"
AGENT_MODE="bedrock"; [[ -z "$MODEL_ID" ]] && AGENT_MODE="template"
CORS="$(state_get amplify_origin)"; CORS="${CORS:-http://localhost:5173}"

put_param AQUA_AGENT             "${AQUA_AGENT:-$AGENT_MODE}"                          String
put_param AQUA_BEDROCK_MODEL_ID  "$(val_or_unset "$MODEL_ID")"                          String
put_param AQUA_PREDICTOR_VERSION "$(val_or_unset "${AQUA_PREDICTOR_VERSION:-$(state_get predictor_version)}")" String
put_param AQUA_THRESHOLDS_URI    "$(val_or_unset "${AQUA_THRESHOLDS_URI:-$(state_get thresholds_uri)}")"       String
put_param AQUA_SIGNATURES_URI    "$(val_or_unset "${AQUA_SIGNATURES_URI:-$(state_get signatures_uri)}")"       String
put_param AQUA_CORS_ORIGINS      "$CORS"                                                String
aws ssm get-parameters-by-path --path "$SSM_PREFIX" --query 'Parameters[].[Name,Type]' --output table
