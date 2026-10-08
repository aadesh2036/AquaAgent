#!/usr/bin/env bash
# =============================================================================
# 12_sagemaker_train.sh — launch the SageMaker Training Job (script mode, PyTorch container)
# BACKBONE:      §3.2 (Training Job), §9.1, G6 ("training job reproducible from S3 inputs")
# Prerequisites: 02,03 done; s3://$AQUA_BUCKET/features/$AQUA_DATASET_VERSION/ populated (module 04 `make features`
#                + upload); AQUA_SM_TRAIN_INSTANCE, AQUA_SM_PT_VERSION, AQUA_SM_PY_VERSION set (<VERIFY>);
#                ml/requirements.txt installed locally (sagemaker SDK); module 06 implemented
# Creates:       SageMaker training job aquaagent-<arch>-<timestamp>; model.tar.gz under s3://…/models/predictor/
# Verify:        aws sagemaker list-training-jobs --name-contains aquaagent --max-results 5
#                aws logs tail /aws/sagemaker/TrainingJobs --since 30m --follow
# Undo:          training jobs cannot be deleted (they stop billing when finished). Remove artifacts with
#                aws s3 rm s3://$AQUA_BUCKET/models/predictor/<model_version>/ --recursive
# Primer:        docs/aws/01_SAGEMAKER_PRIMER.md
# =============================================================================
source "$(dirname "$0")/lib.sh"
require_account
require_var AQUA_SM_TRAIN_INSTANCE; require_var AQUA_SM_PT_VERSION; require_var AQUA_SM_PY_VERSION
export AQUA_BUCKET AQUA_REGION
export AQUA_SM_ROLE_ARN; AQUA_SM_ROLE_ARN="$(state_need sagemaker_role_arn)"
cd "$REPO_ROOT"
python3 -m ml.sagemaker.launch_training --dataset-version "$AQUA_DATASET_VERSION" "$@" \
  || die "launch_training failed (NOT IMPLEMENTED until module 06 — see docs/modules/06_SAGEMAKER.md)"
