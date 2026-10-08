#!/usr/bin/env bash
# =============================================================================
# 00_check_prereqs.sh — verify the terminal can run every later script
# BACKBONE:      §3.3 (local-first), §10.1 (region)
# Prerequisites: infra/env.sh exists (cp infra/env.sh.example infra/env.sh)
# Creates:       nothing (read-only)
# Verify:        PASS/FAIL table printed; exit code 0 only if all REQUIRED checks pass
# Undo:          n/a
# Works in:      CloudShell and local (docker is OPTIONAL — CodeBuild fallback exists)
# =============================================================================
source "$(dirname "$0")/lib.sh"

declare -a ROWS=()
FAILED=0
row() { ROWS+=("$(printf '%-28s %-6s %s' "$1" "$2" "$3")"); [[ "$2" == FAIL && "${4:-required}" == required ]] && FAILED=1; return 0; }

ver_ge() { [[ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" == "$2" ]]; }

# AWS CLI v2
if command -v aws >/dev/null; then
  v="$(aws --version 2>&1 | sed -E 's#aws-cli/([0-9.]+).*#\1#')"
  if ver_ge "$v" "2.0.0"; then row "aws cli v2" PASS "$v"; else row "aws cli v2" FAIL "found $v"; fi
else row "aws cli v2" FAIL "not installed"; fi

# Credentials
if ident="$(aws sts get-caller-identity --query Arn --output text 2>/dev/null)"; then
  row "credentials (sts)" PASS "$ident"
else row "credentials (sts)" FAIL "aws sts get-caller-identity failed"; fi

# Region
if [[ -n "${AWS_REGION:-}" ]]; then row "region" PASS "$AWS_REGION"; else row "region" FAIL "AWS_REGION empty"; fi

# Docker (optional)
if command -v docker >/dev/null && docker info >/dev/null 2>&1; then
  row "docker daemon" PASS "$(docker --version | cut -d, -f1)" optional
else
  row "docker daemon" WARN "unavailable → 05_build_push_images.sh will use CodeBuild fallback" optional
fi

# Python >= 3.10
if command -v python3 >/dev/null; then
  pv="$(python3 -c 'import sys;print("%d.%d.%d"%sys.version_info[:3])')"
  if ver_ge "$pv" "3.10.0"; then row "python >= 3.10" PASS "$pv"; else row "python >= 3.10" FAIL "$pv"; fi
else row "python >= 3.10" FAIL "not installed"; fi

# Node >= 18
if command -v node >/dev/null; then
  nv="$(node --version | tr -d v)"
  if ver_ge "$nv" "18.0.0"; then row "node >= 18" PASS "$nv"; else row "node >= 18" FAIL "$nv"; fi
else row "node >= 18" FAIL "not installed (needed for frontend + TS contract tests)"; fi

# git (image tag = short SHA)
if git -C "$REPO_ROOT" rev-parse --short HEAD >/dev/null 2>&1; then
  row "git repo" PASS "HEAD=$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
else row "git repo" FAIL "not a git repo (image tags need a SHA)"; fi

# zip (CodeBuild fallback source bundle)
command -v zip >/dev/null && row "zip" PASS "$(command -v zip)" optional || row "zip" WARN "missing (only needed for CodeBuild fallback)" optional

echo
printf '%-28s %-6s %s\n' "CHECK" "RESULT" "DETAIL"
printf '%s\n' "----------------------------------------------------------------------------"
printf '%s\n' "${ROWS[@]}"
echo
if [[ $FAILED -eq 0 ]]; then ok "all required prerequisites pass"; else die "fix the FAIL rows above"; fi
