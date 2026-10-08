#!/usr/bin/env bash
# Shared helpers for infra/scripts/*.sh — sourced, never executed directly.
# Provides: env loading, logging to infra/logs/, tagging, state files, idempotency helpers.
set -euo pipefail

INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$INFRA_DIR/.." && pwd)"
STATE_DIR="$INFRA_DIR/.state"
LOG_DIR="$INFRA_DIR/logs"
mkdir -p "$STATE_DIR" "$LOG_DIR"

SCRIPT_NAME="$(basename "${0%.sh}")"
LOG_FILE="$LOG_DIR/${SCRIPT_NAME}_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

if [[ ! -f "$INFRA_DIR/env.sh" ]]; then
  echo "ERROR: $INFRA_DIR/env.sh missing. Run: cp infra/env.sh.example infra/env.sh && edit it" >&2
  exit 1
fi
# shellcheck source=/dev/null
source "$INFRA_DIR/env.sh"

TAG_CLI="Key=${PROJECT_TAG_KEY},Value=${PROJECT_TAG_VALUE}"          # most services
TAG_CLI_LOWER="key=${PROJECT_TAG_KEY},value=${PROJECT_TAG_VALUE}"    # ECS uses lower-case keys

log()  { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
ok()   { printf '[%s] \033[32mOK\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
warn() { printf '[%s] \033[33mWARN\033[0m %s\n' "$(date +%H:%M:%S)" "$*" >&2; }
die()  { printf '[%s] \033[31mERROR\033[0m %s\n' "$(date +%H:%M:%S)" "$*" >&2; exit 1; }

require_cmd() { command -v "$1" >/dev/null 2>&1 || die "missing command: $1"; }
require_var() { [[ -n "${!1:-}" ]] || die "env var $1 is empty — set it in infra/env.sh (see docs/RUNBOOK.md 'Values to confirm')"; }
require_account() { [[ "${ACCOUNT_ID:-UNKNOWN}" != "UNKNOWN" ]] || die "AWS credentials not working (aws sts get-caller-identity failed)"; }

# State: small key files in infra/.state/ shared between scripts (ARNs, ids, URLs).
state_put() { printf '%s' "$2" > "$STATE_DIR/$1"; }
state_get() { [[ -f "$STATE_DIR/$1" ]] && cat "$STATE_DIR/$1" || true; }
state_need() { local v; v="$(state_get "$1")"; [[ -n "$v" ]] || die "state '$1' missing — run the script that creates it first"; printf '%s' "$v"; }

# Render a template with ${VAR} placeholders from the environment (fails on missing vars).
render() {
  python3 - "$1" <<'PY'
import os, string, sys
print(string.Template(open(sys.argv[1]).read()).substitute(os.environ), end="")
PY
}

confirm() {
  local prompt="$1" expect="$2" reply
  read -r -p "$prompt " reply
  [[ "$reply" == "$expect" ]] || die "aborted (expected '$expect')"
}

default_vpc_id() {
  aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text
}
default_subnets_csv() {  # comma-separated default-VPC subnet ids (one per AZ)
  aws ec2 describe-subnets --filters "Name=vpc-id,Values=$(default_vpc_id)" Name=default-for-az,Values=true \
    --query 'Subnets[].SubnetId' --output text | tr '\t' ','
}

log "script=$SCRIPT_NAME account=${ACCOUNT_ID:-?} region=$AWS_REGION profile=${AWS_PROFILE:-<none>} log=$LOG_FILE"
