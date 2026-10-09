#!/usr/bin/env bash
# =============================================================================
# 17_amplify_manual.sh — Amplify Hosting WITHOUT a Git connection (manual zip deployment)
# BACKBONE:      §3.2 (Amplify hosts the frontend, env VITE_API_BASE_URL), G9
# Why:           15_amplify_app.sh needs GitHub OAuth + a pushed repo; this path builds locally and uploads
#                the static bundle (owner request 2026-10-09: no pushes).
# Prerequisites: 10 done for `deploy` (api_url); SSM AQUA_API_KEY (11); node + npm
# Creates:       Amplify app $AMPLIFY_APP_NAME (no repo), branch $AMPLIFY_BRANCH, SPA rewrite rule, deployments
# Usage:         ./17_amplify_manual.sh init     # app + branch; writes amplify_app_id + amplify_origin (CORS)
#                ./17_amplify_manual.sh deploy   # npm run build with VITE_* → zip dist → upload → wait
# Verify:        open "$(cat infra/.state/amplify_origin)"
# Undo:          aws amplify delete-app --app-id "$(cat infra/.state/amplify_app_id)"
# Cost:          Amplify hosting: build minutes not used (local build); storage/transfer pennies at demo scale
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account
CMD="${1:-init}"

# SPA: every route without a file extension serves index.html (/simulate, /city).
RULES='[{"source":"</^[^.]+$|\\.(?!(css|gif|ico|jpg|jpeg|js|png|txt|svg|woff|woff2|ttf|map|json|webp|mp4|webmanifest)$)([^.]+$)/>","target":"/index.html","status":"200"}]'

case "$CMD" in
  init)
    APP_ID="$(aws amplify list-apps --query "apps[?name=='$AMPLIFY_APP_NAME'].appId | [0]" --output text)"
    if [[ "$APP_ID" == "None" || -z "$APP_ID" ]]; then
      APP_ID="$(aws amplify create-app --name "$AMPLIFY_APP_NAME" --platform WEB --custom-rules "$RULES" \
        --tags "${PROJECT_TAG_KEY}=${PROJECT_TAG_VALUE}" --query 'app.appId' --output text)"
      ok "Amplify app created ($APP_ID, no repository — manual deployments)"
    else
      aws amplify update-app --app-id "$APP_ID" --custom-rules "$RULES" >/dev/null
      ok "Amplify app $APP_ID exists (rewrite rule refreshed)"
    fi
    if ! aws amplify get-branch --app-id "$APP_ID" --branch-name "$AMPLIFY_BRANCH" >/dev/null 2>&1; then
      aws amplify create-branch --app-id "$APP_ID" --branch-name "$AMPLIFY_BRANCH" --stage PRODUCTION >/dev/null
      ok "branch $AMPLIFY_BRANCH created"
    fi
    DOMAIN="$(aws amplify get-app --app-id "$APP_ID" --query 'app.defaultDomain' --output text)"
    state_put amplify_app_id "$APP_ID"
    state_put amplify_origin "https://${AMPLIFY_BRANCH}.${DOMAIN}"
    ok "frontend origin: https://${AMPLIFY_BRANCH}.${DOMAIN}  (put it in AQUA_CORS_ORIGINS via 11_ssm_params.sh)"
    ;;
  deploy)
    APP_ID="$(state_need amplify_app_id)"; API_URL="$(state_need api_url)"
    API_KEY="$(aws ssm get-parameter --name "${SSM_PREFIX}/AQUA_API_KEY" --with-decryption --query Parameter.Value --output text)"
    ( cd "$REPO_ROOT/frontend"
      VITE_API_BASE_URL="$API_URL" VITE_API_KEY="$API_KEY" VITE_MOCK_API=false npm run build >/dev/null
      rm -f /tmp/aquaagent_dist.zip && cd dist && zip -qr /tmp/aquaagent_dist.zip . )
    read -r JOB_ID URL < <(aws amplify create-deployment --app-id "$APP_ID" --branch-name "$AMPLIFY_BRANCH" \
      --query '[jobId, zipUploadUrl]' --output text)
    curl -fsS -X PUT -H "Content-Type: application/zip" --data-binary @/tmp/aquaagent_dist.zip "$URL" >/dev/null
    aws amplify start-deployment --app-id "$APP_ID" --branch-name "$AMPLIFY_BRANCH" --job-id "$JOB_ID" >/dev/null
    log "deployment job $JOB_ID started…"
    for _ in $(seq 1 60); do
      ST="$(aws amplify get-job --app-id "$APP_ID" --branch-name "$AMPLIFY_BRANCH" --job-id "$JOB_ID" --query 'job.summary.status' --output text)"
      [[ "$ST" == "SUCCEED" ]] && break
      [[ "$ST" == "FAILED" || "$ST" == "CANCELLED" ]] && die "Amplify job $JOB_ID $ST"
      sleep 5
    done
    rm -f /tmp/aquaagent_dist.zip
    ok "frontend live: $(state_need amplify_origin)  (job $JOB_ID: $ST)"
    ;;
  *) die "usage: $0 init|deploy" ;;
esac
