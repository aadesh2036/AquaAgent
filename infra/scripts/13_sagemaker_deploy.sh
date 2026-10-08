#!/usr/bin/env bash
# =============================================================================
# 13_sagemaker_deploy.sh — deploy the real-time endpoint, then smoke-invoke it with a §7.9 request
# BACKBONE:      §3.2 (real-time endpoint, 1 instance), §7.9, §10.5, G6 (p95 < 300 ms)
# Prerequisites: 12 done (model_version known); AQUA_SM_INFER_INSTANCE set (<VERIFY>); module 06 implemented
# Creates:       SageMaker Model + EndpointConfig + Endpoint $AQUA_PREDICTOR_ENDPOINT
# Verify:        aws sagemaker describe-endpoint --endpoint-name "$AQUA_PREDICTOR_ENDPOINT" --query EndpointStatus
# Undo:          aws sagemaker delete-endpoint --endpoint-name "$AQUA_PREDICTOR_ENDPOINT"   ← BILLS HOURLY, delete after judging
#                (99_teardown.sh also deletes endpoint config + model)
# Usage:         ./13_sagemaker_deploy.sh <model_version>
# CUT LINE (BACKBONE §13, midday Day 3): if the endpoint does not serve → AQUA_MODE=local predictor in the api
#                container; keep the training job as the SageMaker story.
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account; require_var AQUA_SM_INFER_INSTANCE
MODEL_VERSION="${1:-$(state_get predictor_version)}"; [[ -n "$MODEL_VERSION" ]] || die "usage: $0 <model_version>"
export AQUA_SM_ROLE_ARN; AQUA_SM_ROLE_ARN="$(state_need sagemaker_role_arn)"
cd "$REPO_ROOT"
python3 -m ml.sagemaker.deploy_endpoint --model-version "$MODEL_VERSION" --endpoint-name "$AQUA_PREDICTOR_ENDPOINT" \
  || die "deploy_endpoint failed (NOT IMPLEMENTED until module 06)"
state_put predictor_version "$MODEL_VERSION"

log "smoke invoke with the BACKBONE §7.9 example request"
REQ="$(mktemp)"; OUT="$(mktemp)"
python3 - "$MODEL_VERSION" > "$REQ" <<'PY'
import json, sys
ex = json.load(open("shared/contracts/generated/examples.json"))["7.9.request"]
ex["model_version"] = sys.argv[1]
print(json.dumps(ex))
PY
aws sagemaker-runtime invoke-endpoint --endpoint-name "$AQUA_PREDICTOR_ENDPOINT" \
  --content-type application/json --accept application/json --body "fileb://$REQ" "$OUT" >/dev/null
python3 -c "import json,sys; from shared.contracts.models import PredictorResponse; PredictorResponse.model_validate(json.load(open(sys.argv[1]))); print(open(sys.argv[1]).read())" "$OUT"
ok "endpoint returns a §7.9-valid response. Next: python3 -m ml.sagemaker.smoke_invoke --endpoint-name $AQUA_PREDICTOR_ENDPOINT (p95 + parity)"
