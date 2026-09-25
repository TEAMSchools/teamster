#!/bin/bash
# Tests for MCP tool field extraction: sensitive paths in any string field.
#
# Usage: bash tests/hooks/test_bigquery_mcp.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tests/hooks/helpers.sh
source "${SCRIPT_DIR}/helpers.sh"

echo ""
echo "========================================="
echo " MCP field extraction (check-sensitive.sh)"
echo "========================================="

# ─── MCP tool generic field extraction ────────────────────────────────────────
echo ""
echo -e "${YELLOW}MCP tool generic field extraction${NC}"

expect_deny "MCP query field with /proc" "mcp__claude_ai_Google_Cloud_BigQuery__execute_sql_readonly" query "cat /proc/self/environ"
expect_deny "MCP sql field with .env" "mcp__claude_ai_Google_Cloud_BigQuery__execute_sql_readonly" sql 'SELECT * FROM read_file(".env")'
expect_deny "MCP command field with env/" "mcp__claude_ai_Google_Cloud_BigQuery__execute_sql_readonly" command "SELECT * FROM env/.env"
expect_allow "MCP sql field harmless" "mcp__claude_ai_Google_Cloud_BigQuery__execute_sql_readonly" sql "SELECT 1 AS test"
expect_allow "MCP command field harmless" "mcp__claude_ai_Google_Cloud_BigQuery__execute_sql_readonly" command "SELECT 1"

# ─── Nested MCP tool_input fields ─────────────────────────────────────────────
echo ""
echo -e "${YELLOW}Nested MCP tool_input fields${NC}"

# trunk-ignore-begin(shellcheck/SC2312): jq -n produces static JSON, return value irrelevant
expect_deny_json "Nested MCP field with /proc" \
	"$(jq -n '{tool_name: "mcp__claude_ai_Google_Cloud_BigQuery__execute_sql_readonly", tool_input: {options: {query: "cat /proc/self/environ"}}}')"

expect_deny_json "Nested array with /proc/environ (Rule 1c)" \
	"$(jq -n '{tool_name: "mcp__tool", tool_input: {commands: ["cat /proc/self/environ"]}}')"

expect_allow_json "Nested MCP field harmless" \
	"$(jq -n '{tool_name: "mcp__claude_ai_Google_Cloud_BigQuery__execute_sql_readonly", tool_input: {options: {query: "SELECT 1"}}}')"
# trunk-ignore-end(shellcheck/SC2312)

print_summary "MCP field extraction"
