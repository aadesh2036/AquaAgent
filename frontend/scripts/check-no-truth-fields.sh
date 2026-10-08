#!/usr/bin/env bash
# Firewall grep (BACKBONE §11, module 09 §8): the frontend must never read truth fields.
# Matches the property/key forms, not the English word "hidden" in copy or CSS classes.
set -euo pipefail
cd "$(dirname "$0")/.."
PATTERN='\.hidden\b|["'"'"']hidden["'"'"']\s*:|\bLK_'
if grep -RInE "$PATTERN" src/ ; then
  echo "FAIL: truth-field access found in frontend/src" >&2
  exit 1
fi
echo "PASS: no truth-field access in frontend/src"
