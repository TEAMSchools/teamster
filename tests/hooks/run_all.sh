#!/bin/bash
# Runs all hook security test files and reports aggregate results.
#
# Usage: bash tests/hooks/run_all.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

TOTAL_PASS=0
TOTAL_FAIL=0

shopt -s nullglob
test_files=("${SCRIPT_DIR}"/test_*.sh)
shopt -u nullglob

if [[ ${#test_files[@]} -eq 0 ]]; then
  echo -e "${RED}Error: No test files found in ${SCRIPT_DIR}${NC}"
  exit 1
fi

for test_file in "${test_files[@]}"; do

  if bash "${test_file}"; then
    TOTAL_PASS=$((TOTAL_PASS + 1))
  else
    TOTAL_FAIL=$((TOTAL_FAIL + 1))
  fi
done

echo ""
echo "========================================="
echo -e " Overall: ${GREEN}${TOTAL_PASS} suites passed${NC}, ${RED}${TOTAL_FAIL} suites failed${NC}"
echo "========================================="
echo ""

if [[ ${TOTAL_FAIL} -gt 0 ]]; then
  exit 1
fi
