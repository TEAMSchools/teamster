#!/bin/bash
# Tests for fail-closed defaults and tool_name normalization in both hooks
# (issue #4091, Batch 1). A hook that is the sole enforcement layer must DENY
# on inputs it cannot understand — empty stdin, unparseable JSON, non-object
# frames, or a missing tool_name — rather than silently allow. tool_name must
# also be matched case- and whitespace-insensitively so a re-cased name cannot
# skip the Bash / BigQuery gates.
#
# Usage: bash tests/hooks/test_fail_closed.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tests/hooks/helpers.sh
source "${SCRIPT_DIR}/helpers.sh"

echo ""
echo "========================================="
echo " Fail-closed defaults + tool_name normalization"
echo "========================================="

# ─── check-sensitive.sh: fail closed on un-understandable input ──────────────
echo ""
echo -e "${YELLOW}PreToolUse: fail closed on malformed input${NC}"

expect_deny_raw "PreToolUse empty stdin" "${HOOK}" ""
expect_deny_raw "PreToolUse non-JSON text" "${HOOK}" "not json at all"
expect_deny_raw "PreToolUse truncated JSON" "${HOOK}" '{"tool_name": "Bash", "tool_inp'
expect_deny_raw "PreToolUse non-object (array)" "${HOOK}" '[]'
expect_deny_raw "PreToolUse non-object (string)" "${HOOK}" '"just a string"'
expect_deny_raw "PreToolUse null literal" "${HOOK}" 'null'
expect_deny_raw "PreToolUse missing tool_name" "${HOOK}" \
  '{"tool_input": {"command": "echo hi"}}'
expect_deny_raw "PreToolUse null tool_name" "${HOOK}" \
  '{"tool_name": null, "tool_input": {"command": "echo hi"}}'

# ─── check-sensitive.sh: tool_name normalization ─────────────────────────────
echo ""
echo -e "${YELLOW}PreToolUse: tool_name normalization (case/whitespace)${NC}"

# BigQuery write gate must fire regardless of casing/whitespace on the name.
expect_deny_raw "BQ gate: mixed-case tool_name + DROP" "${HOOK}" \
  '{"tool_name": "MCP__BigQuery__Execute_SQL", "tool_input": {"sql": "DROP TABLE dataset.t"}}'
expect_deny_raw "BQ gate: padded tool_name + DROP" "${HOOK}" \
  '{"tool_name": "  mcp__bigquery__execute_sql  ", "tool_input": {"sql": "DROP TABLE dataset.t"}}'
# Bash command rules must fire regardless of casing on the name.
expect_deny_raw "Bash gate: upper-case BASH + printenv" "${HOOK}" \
  '{"tool_name": "BASH", "tool_input": {"command": "printenv"}}'

# Controls — normalization must NOT change correct decisions.
expect_deny "CONTROL Bash printenv still denied" Bash command "printenv"
expect_allow "CONTROL execute_sql SELECT still allowed" \
  "mcp__bigquery__execute_sql" sql "SELECT 1 AS test"

# ─── check-output.sh: fail closed on un-understandable input ─────────────────
echo ""
echo -e "${YELLOW}PostToolUse: fail closed on malformed input${NC}"

expect_deny_raw "PostToolUse empty stdin" "${OUTPUT_HOOK}" ""
expect_deny_raw "PostToolUse non-JSON text" "${OUTPUT_HOOK}" "not json at all"
expect_deny_raw "PostToolUse non-object (array)" "${OUTPUT_HOOK}" '[]'
expect_deny_raw "PostToolUse missing tool_name + secret" "${OUTPUT_HOOK}" \
  '{"tool_response": {"x": "op://vault/item/field"}}'
expect_deny_raw "PostToolUse null tool_name + secret" "${OUTPUT_HOOK}" \
  '{"tool_name": null, "tool_response": {"x": "op://vault/item/field"}}'

# ─── check-output.sh: tool_name normalization ────────────────────────────────
echo ""
echo -e "${YELLOW}PostToolUse: tool_name normalization (case)${NC}"

expect_deny_raw "scan gate: upper-case BASH + secret" "${OUTPUT_HOOK}" \
  '{"tool_name": "BASH", "tool_response": {"stdout": "op://vault/item/field"}}'

# Controls — a genuinely non-scanned tool must still pass through unscanned.
expect_allow_raw "CONTROL Edit output stays unscanned" "${OUTPUT_HOOK}" \
  '{"tool_name": "Edit", "tool_response": {"x": "op://vault/item/field"}}'
expect_deny_raw "CONTROL Bash + secret still denied" "${OUTPUT_HOOK}" \
  '{"tool_name": "Bash", "tool_response": {"stdout": "op://vault/item/field"}}'

print_summary "Fail-closed + Normalization"
