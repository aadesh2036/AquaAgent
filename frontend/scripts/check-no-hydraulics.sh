#!/usr/bin/env bash
# G9 grep check (BACKBONE P1, §7.15): the frontend must not compute hydraulic values.
# Fails if src/ contains hydraulic formulas/keywords. Formatting via @units is allowed.
set -euo pipefail
cd "$(dirname "$0")/.."
PATTERN='hazen|darcy|headloss *=|head_loss *=|Math\.pow\([^)]*1\.852|4\.727|10\.67|sqrt\( *2 *\* *9\.8|9\.81|bernoulli|reynolds|pressure_m *[-+*/]=|flow_lps *[-+*/]=|demand_lps *[-+*/]='
if grep -RInEi "$PATTERN" src/ ; then
  echo "FAIL: hydraulic arithmetic found in frontend/src (BACKBONE P1)" >&2
  exit 1
fi
echo "PASS: no hydraulic math in frontend/src"
