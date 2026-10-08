#!/usr/bin/env bash
# =============================================================================
# 10_apigw_https.sh — API Gateway HTTP API: HTTPS front door proxying to the HTTP ALB
# BACKBONE:      §3.2 (mixed content: Amplify is HTTPS, raw ALB is HTTP), §7.14.1, G3
#                BACKBONE_ISSUES BI-04 (30 s integration timeout), BI-12 (CORS owned by FastAPI), BI-13
# Prerequisites: 08 done (ALB DNS)
# Creates:       HTTP API $APIGW_NAME, HTTP_PROXY integration → http://<alb>/{proxy}, route ANY /{proxy+},
#                stage $default (auto-deploy, throttled)
# Verify:        curl "$(cat infra/.state/api_url)/api/health"     ← G3 check
# Undo:          aws apigatewayv2 delete-api --api-id "$(cat infra/.state/api_id)"
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account
ALB_DNS="$(state_need alb_dns)"

API_ID="$(aws apigatewayv2 get-apis --query "Items[?Name=='$APIGW_NAME'].ApiId | [0]" --output text)"
if [[ "$API_ID" == "None" || -z "$API_ID" ]]; then
  # No --cors-configuration on purpose: FastAPI owns CORS (BI-12); OPTIONS passes through to the ALB.
  API_ID="$(aws apigatewayv2 create-api --name "$APIGW_NAME" --protocol-type HTTP \
    --tags "${PROJECT_TAG_KEY}=${PROJECT_TAG_VALUE}" --query ApiId --output text)"
  ok "HTTP API created ($API_ID)"
fi

INTEG_ID="$(aws apigatewayv2 get-integrations --api-id "$API_ID" --query 'Items[0].IntegrationId' --output text)"
if [[ "$INTEG_ID" == "None" || -z "$INTEG_ID" ]]; then
  INTEG_ID="$(aws apigatewayv2 create-integration --api-id "$API_ID" --integration-type HTTP_PROXY \
    --integration-method ANY --integration-uri "http://${ALB_DNS}/{proxy}" \
    --payload-format-version 1.0 --query IntegrationId --output text)"
  ok "integration created → http://${ALB_DNS}/{proxy}"
else
  aws apigatewayv2 update-integration --api-id "$API_ID" --integration-id "$INTEG_ID" \
    --integration-uri "http://${ALB_DNS}/{proxy}" >/dev/null
fi

if [[ "$(aws apigatewayv2 get-routes --api-id "$API_ID" --query "Items[?RouteKey=='ANY /{proxy+}'] | length(@)" --output text)" == "0" ]]; then
  aws apigatewayv2 create-route --api-id "$API_ID" --route-key 'ANY /{proxy+}' --target "integrations/$INTEG_ID" >/dev/null
  ok "route ANY /{proxy+} created"
fi

if ! aws apigatewayv2 get-stage --api-id "$API_ID" --stage-name '$default' >/dev/null 2>&1; then
  aws apigatewayv2 create-stage --api-id "$API_ID" --stage-name '$default' --auto-deploy \
    --tags "${PROJECT_TAG_KEY}=${PROJECT_TAG_VALUE}" >/dev/null
  ok "stage \$default created"
fi
if [[ -n "${APIGW_THROTTLE_BURST:-}" && -n "${APIGW_THROTTLE_RATE:-}" ]]; then
  aws apigatewayv2 update-stage --api-id "$API_ID" --stage-name '$default' \
    --default-route-settings "ThrottlingBurstLimit=${APIGW_THROTTLE_BURST},ThrottlingRateLimit=${APIGW_THROTTLE_RATE}" >/dev/null
  ok "throttling burst=$APIGW_THROTTLE_BURST rate=$APIGW_THROTTLE_RATE"
else
  warn "APIGW_THROTTLE_* not set — no stage throttling (BI-13)"
fi

API_URL="$(aws apigatewayv2 get-api --api-id "$API_ID" --query ApiEndpoint --output text)"
state_put api_id "$API_ID"; state_put api_url "$API_URL"
ok "HTTPS base URL: $API_URL   (VITE_API_BASE_URL)"
curl -fsS "$API_URL/api/health" && echo && ok "G3: public HTTPS health OK" || warn "health not OK yet (is 09 done and healthy?)"
