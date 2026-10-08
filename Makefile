# AquaAgent Makefile — index of every terminal workflow (docs/RUNBOOK.md).
# NOTE: the repo path may contain spaces; every recipe uses paths relative to the repo root.
SHELL := /bin/bash
.DEFAULT_GOAL := help
PY    ?= .venv/bin/python
PIP   ?= .venv/bin/pip
N     ?= 20
DS    ?= ds1
NOT_IMPL = @echo "NOT IMPLEMENTED — see docs/modules/$(1)" >&2; exit 2

.PHONY: help setup setup-ml setup-api feasibility datagen-ds1 sim-serve api-serve tune mvp lint test contracts-test sim-smoke datagen-local compose-up compose-down features \
        train-local aws-prereqs aws-bootstrap images datagen-aws sm-train sm-deploy bedrock-check \
        deploy-api deploy-frontend status teardown

help: ## list targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n",$$1,$$2}'

# ---------------------------------------------------------------- local dev
PYVER ?= 3.12

setup: ## Python 3.12 venv (uv if available) + dev + sim deps (+ frontend deps if npm present)
	@if command -v uv >/dev/null; then uv venv --python $(PYVER) .venv && VIRTUAL_ENV=.venv uv pip install -q -r requirements-dev.txt -r sim/requirements.txt; \
	 else python$(PYVER) -m venv .venv && $(PIP) install -q --upgrade pip && $(PIP) install -q -r requirements-dev.txt -r sim/requirements.txt; fi
	@$(PY) -c "import sys, wntr; assert sys.version_info[:2] == (3, 12), sys.version; print('python', sys.version.split()[0], 'wntr', wntr.__version__)"
	@test -f .env || cp .env.example .env
	@test -f infra/env.sh || cp infra/env.sh.example infra/env.sh
	@command -v npm >/dev/null && (cd frontend && npm install --silent) || echo "npm not found — skipping frontend deps"

lint: ## ruff + bash -n on infra scripts
	$(PY) -m ruff check .
	@for f in infra/scripts/*.sh; do bash -n "$$f" || exit 1; done
	@echo "lint OK"

test: contracts-test ## all unit tests (shared + sim + ml + api)
	$(PY) -m pytest

contracts-test: ## BACKBONE JSON examples round-trip through Pydantic; TS enum parity; units
	$(PY) -m shared.contracts.export
	$(PY) -m pytest shared/tests
	node --test shared/tests/*.test.ts

# ---------------------------------------------------------------- modules (local)
sim-smoke: ## G1 smoke: build EPA net, 24 h EPS, leaks, mass balance (module 01)
	$(PY) -m sim.smoke

datagen-local: ## generate N sims locally (default N=20) → data/raw/$(DS) (module 02)
	$(PY) -m sim.cli generate --config config/generation/$(DS).yaml --shard 0 --num-shards 1 --limit $(N) --out data/raw/$(DS)/shard=0/

datagen-ds1: ## full ds1 locally: parallel shards + merge (module 02; SHARDS=8)
	bash scripts/datagen_local.sh $(or $(SHARDS),8) $(DS)

sim-serve: ## run the sim server on :8000 (module 01)
	$(PY) -m sim.cli serve --port 8000

api-serve: ## run the orchestrator on :8080, AQUA_MODE=local (module 08)
	set -a; [ -f .env ] && . ./.env; set +a; $(PY) -m uvicorn api.app.main:app --port 8080 --reload

tune: ## tune RTCA thresholds on val, then freeze (module 05)
	$(call NOT_IMPL,05_ANOMALY_LOCALISATION.md)

mvp: ## gate MVP: 3 challenge runs against the local stack (module 08)
	$(PY) -m api.scripts.e2e_challenge --base http://localhost:8080 --runs 3

compose-up: ## local stack: sim:8000 api:8080 frontend:5173
	docker compose up --build -d
	@echo "frontend http://localhost:5173  api http://localhost:8080/api/health"

compose-down: ## stop local stack
	docker compose down

features: ## build GraphSample tensors + scalers from processed/ (module 04)
	$(call NOT_IMPL,04_ML_PREDICTOR.md)

setup-ml: ## add ML deps (torch CPU, sklearn) to .venv — module 04 onwards
	@if command -v uv >/dev/null; then VIRTUAL_ENV=.venv uv pip install -q -r ml/requirements.txt; else $(PIP) install -q -r ml/requirements.txt; fi

setup-api: ## add API deps (fastapi, httpx, boto3) to .venv — module 08 onwards
	@if command -v uv >/dev/null; then VIRTUAL_ENV=.venv uv pip install -q -r api/requirements.txt; else $(PIP) install -q -r api/requirements.txt; fi

feasibility: ## re-run the WNTR feasibility spike (docs/research/WNTR_FEASIBILITY.md)
	$(PY) docs/research/wntr_feasibility_spike.py

train-local: ## run ml/predictor/train.py locally with local defaults (module 04)
	$(PY) -m ml.predictor.train --arch mlp

# ---------------------------------------------------------------- AWS
aws-prereqs: ## 00: PASS/FAIL table of terminal prerequisites
	bash infra/scripts/00_check_prereqs.sh

aws-bootstrap: ## 01–04: budget, bucket, IAM roles, ECR repos
	bash infra/scripts/01_budget_alert.sh
	bash infra/scripts/02_s3_bucket.sh
	bash infra/scripts/03_iam_roles.sh
	bash infra/scripts/04_ecr_repos.sh

images: ## 05: build + push both images (docker or CodeBuild fallback)
	bash infra/scripts/05_build_push_images.sh

datagen-aws: ## (T3) 06–07: ECS RunTask generate shards + merge — T1 uses datagen-local
	bash infra/scripts/06_ecs_cluster.sh
	bash infra/scripts/07_run_datagen.sh

sm-train: ## 12: SageMaker training job (module 06)
	bash infra/scripts/12_sagemaker_train.sh

sm-deploy: ## 13: real-time endpoint + smoke invoke (module 06) — usage: make sm-deploy MV=<model_version>
	bash infra/scripts/13_sagemaker_deploy.sh $(MV)

bedrock-check: ## 14: region/model access + Converse smoke (module 07)
	bash infra/scripts/14_bedrock_check.sh

deploy-api: ## 06, 08, 11, 09, 10: cluster, ALB, SSM, service, API Gateway
	bash infra/scripts/06_ecs_cluster.sh
	bash infra/scripts/08_network_alb.sh
	bash infra/scripts/11_ssm_params.sh
	bash infra/scripts/09_ecs_service.sh
	bash infra/scripts/10_apigw_https.sh

deploy-frontend: ## 15: Amplify app/branch/env + release build
	bash infra/scripts/15_amplify_app.sh

status: ## 90: one-screen status
	bash infra/scripts/90_status.sh

teardown: ## 99: ordered deletion (asks confirmation; keeps S3 unless ARGS=--purge)
	bash infra/scripts/99_teardown.sh $(ARGS)
