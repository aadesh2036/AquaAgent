#!/usr/bin/env bash
# =============================================================================
# 15_amplify_app.sh — Amplify Hosting app + branch + VITE_API_BASE_URL
# BACKBONE:      §3.2 (Amplify, branch main, env VITE_API_BASE_URL), G9
# Prerequisites: 10 done (api_url); repo pushed to GitHub (you manage branches); amplify.yml at repo root
# Creates:       Amplify app $AMPLIFY_APP_NAME, branch $AMPLIFY_BRANCH, env vars; writes amplify_origin state
# Verify:        aws amplify list-jobs --app-id "$(cat infra/.state/amplify_app_id)" --branch-name main --max-items 3
#                open https://$AMPLIFY_BRANCH.<appId>.amplifyapp.com
# Undo:          aws amplify delete-app --app-id "$(cat infra/.state/amplify_app_id)"
#
# ┌──────────────────────────────── MANUAL STEP ────────────────────────────────┐
# │ Connecting Amplify to GitHub needs OAuth. EITHER                              │
# │  (a) set GITHUB_REPO_URL and export GITHUB_TOKEN (fine-grained PAT with repo  │
# │      read + webhooks) before running — the script passes --access-token; OR   │
# │  (b) run this script once (creates the app without a repo), then open        │
# │      Amplify console → app "aquaagent" → "Connect repository" → GitHub →      │
# │      authorise → pick repo + branch "main" → "monorepo" root = frontend.      │
# │ After connecting, re-run this script to (re)apply env vars and start a build. │
# └──────────────────────────────────────────────────────────────────────────────┘
# After it deploys: re-run 11_ssm_params.sh then 09_ecs_service.sh so CORS allows the Amplify origin.
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account
API_URL="$(state_need api_url)"
API_KEY="$(aws ssm get-parameter --name "${SSM_PREFIX}/AQUA_API_KEY" --with-decryption --query Parameter.Value --output text 2>/dev/null || true)"
ENV_VARS="VITE_API_BASE_URL=${API_URL},VITE_MOCK_API=false,VITE_API_KEY=${API_KEY},AMPLIFY_MONOREPO_APP_ROOT=frontend"

APP_ID="$(aws amplify list-apps --query "apps[?name=='$AMPLIFY_APP_NAME'].appId | [0]" --output text)"
if [[ "$APP_ID" == "None" || -z "$APP_ID" ]]; then
  ARGS=(--name "$AMPLIFY_APP_NAME" --platform WEB --environment-variables "$ENV_VARS"
        --tags "${PROJECT_TAG_KEY}=${PROJECT_TAG_VALUE}")
  if [[ -n "${GITHUB_REPO_URL:-}" && -n "${GITHUB_TOKEN:-}" ]]; then
    ARGS+=(--repository "$GITHUB_REPO_URL" --access-token "$GITHUB_TOKEN")
  else
    warn "GITHUB_REPO_URL/GITHUB_TOKEN not set → creating app without repo. Follow the MANUAL STEP box."
  fi
  APP_ID="$(aws amplify create-app "${ARGS[@]}" --query 'app.appId' --output text)"
  ok "Amplify app created ($APP_ID)"
else
  aws amplify update-app --app-id "$APP_ID" --environment-variables "$ENV_VARS" >/dev/null
  ok "Amplify app $APP_ID env updated"
fi
state_put amplify_app_id "$APP_ID"

REPO="$(aws amplify get-app --app-id "$APP_ID" --query 'app.repository' --output text)"
if [[ "$REPO" == "None" || -z "$REPO" ]]; then
  warn "no repository connected yet — complete the MANUAL STEP, then re-run."; exit 0
fi

if ! aws amplify get-branch --app-id "$APP_ID" --branch-name "$AMPLIFY_BRANCH" >/dev/null 2>&1; then
  aws amplify create-branch --app-id "$APP_ID" --branch-name "$AMPLIFY_BRANCH" --stage PRODUCTION \
    --enable-auto-build --framework React >/dev/null
  ok "branch $AMPLIFY_BRANCH created"
fi
aws amplify start-job --app-id "$APP_ID" --branch-name "$AMPLIFY_BRANCH" --job-type RELEASE --query 'jobSummary.jobId' --output text
DOMAIN="$(aws amplify get-app --app-id "$APP_ID" --query 'app.defaultDomain' --output text)"
state_put amplify_origin "https://${AMPLIFY_BRANCH}.${DOMAIN}"
ok "frontend will be at https://${AMPLIFY_BRANCH}.${DOMAIN}  → now re-run 11_ssm_params.sh + 09_ecs_service.sh (CORS)"
