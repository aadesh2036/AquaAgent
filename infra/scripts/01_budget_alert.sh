#!/usr/bin/env bash
# =============================================================================
# 01_budget_alert.sh — monthly cost budget with an email alert at 80 % actual / 100 % forecast
# BACKBONE:      §10.5 (cost guardrails), G3 ("budget alert active")
# Prerequisites: 00 passes; BUDGET_EMAIL and BUDGET_LIMIT_USD set in infra/env.sh
# Creates:       AWS Budgets budget "$BUDGET_NAME" (+ 2 email notifications)
# Verify:        aws budgets describe-budget --account-id "$ACCOUNT_ID" --budget-name "$BUDGET_NAME"
#                (AWS sends a subscription email — nothing to confirm for Budgets, but check spam)
# Undo:          aws budgets delete-budget --account-id "$ACCOUNT_ID" --budget-name "$BUDGET_NAME"
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account; require_var BUDGET_EMAIL; require_var BUDGET_LIMIT_USD

if aws budgets describe-budget --account-id "$ACCOUNT_ID" --budget-name "$BUDGET_NAME" >/dev/null 2>&1; then
  ok "budget $BUDGET_NAME already exists — skipping"
  exit 0
fi

BUDGET_JSON=$(cat <<JSON
{"BudgetName":"$BUDGET_NAME","BudgetLimit":{"Amount":"$BUDGET_LIMIT_USD","Unit":"USD"},
 "TimeUnit":"MONTHLY","BudgetType":"COST"}
JSON
)
NOTIF_JSON=$(cat <<JSON
[
 {"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":80,"ThresholdType":"PERCENTAGE"},
  "Subscribers":[{"SubscriptionType":"EMAIL","Address":"$BUDGET_EMAIL"}]},
 {"Notification":{"NotificationType":"FORECASTED","ComparisonOperator":"GREATER_THAN","Threshold":100,"ThresholdType":"PERCENTAGE"},
  "Subscribers":[{"SubscriptionType":"EMAIL","Address":"$BUDGET_EMAIL"}]}
]
JSON
)
aws budgets create-budget --account-id "$ACCOUNT_ID" \
  --budget "$BUDGET_JSON" --notifications-with-subscribers "$NOTIF_JSON"
ok "budget $BUDGET_NAME created: \$$BUDGET_LIMIT_USD/month → $BUDGET_EMAIL"
