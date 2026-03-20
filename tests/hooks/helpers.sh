#!/bin/bash
# Shared test helpers for hook security tests.
# Source this file from individual test scripts.

set -uo pipefail

HOOK=".claude/hooks/check-sensitive.sh"
OUTPUT_HOOK=".claude/hooks/check-output.sh"
PASS=0
FAIL=0
ERRORS=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
# trunk-ignore(shellcheck/SC2034): exported via source to test files
YELLOW='\033[1;33m'
NC='\033[0m'

# Helper: build JSON input for the hook
make_input() {
  local tool_name="$1"
  local field="$2"
  local value="$3"
  jq -n --arg tn "${tool_name}" --arg fld "${field}" --arg val "${value}" \
    '{tool_name: $tn, tool_input: {($fld): $val}}'
}

# Helper: build JSON input with two fields (for Write/Edit tools)
make_input2() {
  local tool_name="$1"
  local field1="$2" value1="$3"
  local field2="$4" value2="$5"
  jq -n --arg tn "${tool_name}" \
    --arg f1 "${field1}" --arg v1 "${value1}" \
    --arg f2 "${field2}" --arg v2 "${value2}" \
    '{tool_name: $tn, tool_input: {($f1): $v1, ($f2): $v2}}'
}

# Run hook with pre-built JSON and check result
# expect_deny_json <description> <json>
expect_deny_json() {
  local desc="$1" input="$2"
  if echo "${input}" | bash "${HOOK}" >/dev/null 2>&1; then
    FAIL=$((FAIL + 1))
    ERRORS+="\n  ${RED}FAIL${NC} [should deny]: ${desc}"
  else
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}PASS${NC} [deny]: ${desc}"
  fi
}

expect_allow_json() {
  local desc="$1" input="$2"
  if echo "${input}" | bash "${HOOK}" >/dev/null 2>&1; then
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}PASS${NC} [allow]: ${desc}"
  else
    FAIL=$((FAIL + 1))
    ERRORS+="\n  ${RED}FAIL${NC} [should allow]: ${desc}"
  fi
}

# Run hook with two-field input and check result
expect_deny2() {
  local desc="$1" tool="$2" f1="$3" v1="$4" f2="$5" v2="$6"
  local input
  input=$(make_input2 "${tool}" "${f1}" "${v1}" "${f2}" "${v2}")
  if echo "${input}" | bash "${HOOK}" >/dev/null 2>&1; then
    FAIL=$((FAIL + 1))
    ERRORS+="\n  ${RED}FAIL${NC} [should deny]: ${desc}"
  else
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}PASS${NC} [deny]: ${desc}"
  fi
}

expect_allow2() {
  local desc="$1" tool="$2" f1="$3" v1="$4" f2="$5" v2="$6"
  local input
  input=$(make_input2 "${tool}" "${f1}" "${v1}" "${f2}" "${v2}")
  if echo "${input}" | bash "${HOOK}" >/dev/null 2>&1; then
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}PASS${NC} [allow]: ${desc}"
  else
    FAIL=$((FAIL + 1))
    ERRORS+="\n  ${RED}FAIL${NC} [should allow]: ${desc}"
  fi
}

# Run hook and check result
# expect_deny <description> <tool_name> <field> <value>
expect_deny() {
  local desc="$1" tool="$2" field="$3" value="$4"
  local input
  input=$(make_input "${tool}" "${field}" "${value}")
  if echo "${input}" | bash "${HOOK}" >/dev/null 2>&1; then
    FAIL=$((FAIL + 1))
    ERRORS+="\n  ${RED}FAIL${NC} [should deny]: ${desc}"
    ERRORS+="\n       tool=${tool} ${field}=$(echo "${value}" | head -c 80)"
  else
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}PASS${NC} [deny]: ${desc}"
  fi
}

expect_allow() {
  local desc="$1" tool="$2" field="$3" value="$4"
  local input
  input=$(make_input "${tool}" "${field}" "${value}")
  if echo "${input}" | bash "${HOOK}" >/dev/null 2>&1; then
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}PASS${NC} [allow]: ${desc}"
  else
    FAIL=$((FAIL + 1))
    ERRORS+="\n  ${RED}FAIL${NC} [should allow]: ${desc}"
    ERRORS+="\n       tool=${tool} ${field}=$(echo "${value}" | head -c 80)"
  fi
}

# PostToolUse helper
# check_output <desc> <expect> [tool] <content>
# 3-arg form: check_output "desc" deny|clean "output"        (defaults to Bash)
# 4-arg form: check_output "desc" deny|clean Tool "output"
check_output() {
  local desc="$1" expect="$2" tool content_val
  if [[ $# -eq 3 ]]; then
    tool="Bash"
    content_val="$3"
  else
    tool="$3"
    content_val="$4"
  fi
  local input
  input=$(jq -n --arg tn "${tool}" --arg c "${content_val}" \
    '{tool_name: $tn, tool_output: {content: $c, stdout: $c, stderr: ""}}')

  if echo "${input}" | bash "${OUTPUT_HOOK}" >/dev/null 2>&1; then
    local exited_ok=true
  else
    local exited_ok=false
  fi

  if [[ ${expect} == "deny" && ${exited_ok} == "false" ]]; then
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}PASS${NC} [deny]: ${desc}"
  elif [[ ${expect} == "clean" && ${exited_ok} == "true" ]]; then
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}PASS${NC} [clean]: ${desc}"
  else
    FAIL=$((FAIL + 1))
    ERRORS+="\n  ${RED}FAIL${NC} [expected ${expect}]: ${desc}"
  fi
}

# Print summary and exit with appropriate code
print_summary() {
  local label="${1:-Hook Security Tests}"
  echo ""
  echo "========================================="
  echo -e " ${label}: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}"
  echo "========================================="

  if [[ ${FAIL} -gt 0 ]]; then
    echo -e "\nFailures:${ERRORS}"
    echo ""
    exit 1
  else
    echo -e "\n${GREEN}All tests passed.${NC}"
    echo ""
    exit 0
  fi
}
