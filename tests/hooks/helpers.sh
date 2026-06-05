#!/bin/bash
# Shared test helpers for hook security tests.
# Source this file from individual test scripts.

set -uo pipefail

# Default to the real hooks; allow override via env so a candidate patch can be
# validated against the whole suite before it is applied to the protected files.
HOOK="${HOOK:-.claude/hooks/check-sensitive.sh}"
OUTPUT_HOOK="${OUTPUT_HOOK:-.claude/hooks/check-output.sh}"
PASS=0
FAIL=0
ERRORS=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
# trunk-ignore(shellcheck/SC2034): exported via source to test files
YELLOW='\033[1;33m'
NC='\033[0m'

# Helper: check if hook stdout contains a deny decision
_is_deny() {
  grep -q '"permissionDecision"' <<<"$1" && grep -q '"deny"' <<<"$1"
}

# Assert that a hook deny exits 0 with deny JSON on stdout (not exit 1/stderr).
# Claude Code treats exit 1 as a non-blocking error — only exit 0 + JSON is honored.
# Usage: expect_deny_exit0 <description> <hook_script> <json_input>
expect_deny_exit0() {
  local desc="$1" hook="$2" input="$3"
  local stdout stderr exit_code tmpfile
  # Per-invocation temp file (mktemp) — a fixed /tmp path races under parallel runs.
  tmpfile=$(mktemp)
  stdout=$(printf '%s' "${input}" | bash "${hook}" 2>"${tmpfile}")
  exit_code=$?
  stderr=$(cat "${tmpfile}")
  rm -f "${tmpfile}"
  local ok=true
  if [[ ${exit_code} -ne 0 ]]; then
    ok=false
    FAIL=$((FAIL + 1))
    ERRORS+="\n  ${RED}FAIL${NC} [exit 0]: ${desc} (got exit ${exit_code} — Claude Code ignores non-zero)"
  elif ! _is_deny "${stdout}"; then
    ok=false
    FAIL=$((FAIL + 1))
    ERRORS+="\n  ${RED}FAIL${NC} [deny JSON on stdout]: ${desc} (stdout empty or missing deny)"
  elif echo "${stderr}" | grep -q 'permissionDecision'; then
    ok=false
    FAIL=$((FAIL + 1))
    ERRORS+="\n  ${RED}FAIL${NC} [no deny on stderr]: ${desc} (deny JSON leaked to stderr)"
  fi
  if [[ ${ok} == "true" ]]; then
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}PASS${NC} [exit 0 + deny on stdout]: ${desc}"
  fi
}

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
  # Validate the full protocol (exit 0 + deny on stdout + not on stderr).
  expect_deny_exit0 "${desc}" "${HOOK}" "${input}"
}

expect_allow_json() {
  local desc="$1" input="$2"
  local output
  output=$(echo "${input}" | bash "${HOOK}" 2>/dev/null)
  if _is_deny "${output}"; then
    FAIL=$((FAIL + 1))
    ERRORS+="\n  ${RED}FAIL${NC} [should allow]: ${desc}"
  else
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}PASS${NC} [allow]: ${desc}"
  fi
}

# Pipe an arbitrary raw string to a named hook and assert it denies.
# Used for fail-closed cases (empty/malformed/non-object/missing tool_name)
# and tool_name normalization that the JSON-builder helpers can't express.
# Usage: expect_deny_raw <description> <hook_script> <raw_input>
expect_deny_raw() {
  local desc="$1" hook="$2" input="$3"
  expect_deny_exit0 "${desc}" "${hook}" "${input}"
}

# Pipe an arbitrary raw string to a named hook and assert it allows.
# Usage: expect_allow_raw <description> <hook_script> <raw_input>
expect_allow_raw() {
  local desc="$1" hook="$2" input="$3"
  local output
  output=$(printf '%s' "${input}" | bash "${hook}" 2>/dev/null)
  if _is_deny "${output}"; then
    FAIL=$((FAIL + 1))
    ERRORS+="\n  ${RED}FAIL${NC} [should allow]: ${desc}"
  else
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}PASS${NC} [allow]: ${desc}"
  fi
}

# Run hook with two-field input and check result
expect_deny2() {
  local desc="$1" tool="$2" f1="$3" v1="$4" f2="$5" v2="$6"
  local input
  input=$(make_input2 "${tool}" "${f1}" "${v1}" "${f2}" "${v2}")
  expect_deny_exit0 "${desc}" "${HOOK}" "${input}"
}

expect_allow2() {
  local desc="$1" tool="$2" f1="$3" v1="$4" f2="$5" v2="$6"
  local input output
  input=$(make_input2 "${tool}" "${f1}" "${v1}" "${f2}" "${v2}")
  output=$(echo "${input}" | bash "${HOOK}" 2>/dev/null)
  if _is_deny "${output}"; then
    FAIL=$((FAIL + 1))
    ERRORS+="\n  ${RED}FAIL${NC} [should allow]: ${desc}"
  else
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}PASS${NC} [allow]: ${desc}"
  fi
}

# Run hook and check result
# expect_deny <description> <tool_name> <field> <value>
expect_deny() {
  local desc="$1" tool="$2" field="$3" value="$4"
  local input
  input=$(make_input "${tool}" "${field}" "${value}")
  expect_deny_exit0 "${desc}" "${HOOK}" "${input}"
}

expect_allow() {
  local desc="$1" tool="$2" field="$3" value="$4"
  local input output
  input=$(make_input "${tool}" "${field}" "${value}")
  output=$(echo "${input}" | bash "${HOOK}" 2>/dev/null)
  if _is_deny "${output}"; then
    FAIL=$((FAIL + 1))
    ERRORS+="\n  ${RED}FAIL${NC} [should allow]: ${desc}"
    ERRORS+="\n       tool=${tool} ${field}=$(echo "${value}" | head -c 80)"
  else
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}PASS${NC} [allow]: ${desc}"
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
    '{tool_name: $tn, tool_response: {content: $c, stdout: $c, stderr: ""}}')

  if [[ ${expect} == "deny" ]]; then
    # Full protocol: exit 0 + deny on stdout + not on stderr.
    expect_deny_exit0 "${desc}" "${OUTPUT_HOOK}" "${input}"
  else
    local output
    output=$(printf '%s' "${input}" | bash "${OUTPUT_HOOK}" 2>/dev/null)
    if _is_deny "${output}"; then
      FAIL=$((FAIL + 1))
      ERRORS+="\n  ${RED}FAIL${NC} [expected clean]: ${desc}"
    else
      PASS=$((PASS + 1))
      echo -e "  ${GREEN}PASS${NC} [clean]: ${desc}"
    fi
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
