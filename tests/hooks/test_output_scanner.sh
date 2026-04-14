#!/bin/bash
# Tests for PostToolUse output scanner (check-output.sh):
# secret patterns, token detection, connection strings, high-entropy heuristic.
#
# Usage: bash tests/hooks/test_output_scanner.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tests/hooks/helpers.sh
source "${SCRIPT_DIR}/helpers.sh"

echo ""
echo "========================================="
echo " Output Scanner (check-output.sh)"
echo "========================================="

if [[ ! -f ${OUTPUT_HOOK} ]]; then
  echo -e "  ${YELLOW}SKIP${NC}: ${OUTPUT_HOOK} not found"
  exit 0
fi

# ─── Secret pattern detection ────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}PostToolUse: Secret pattern detection${NC}"

check_output "op:// reference in output" deny "op://vault/item/field"
# synthetic test fixture, not a real key
# trunk-ignore(gitleaks/private-key)
check_output "private key header" deny "-----BEGIN RSA PRIVATE KEY-----"
check_output "EC private key" deny "-----BEGIN EC PRIVATE KEY-----"
check_output "OPENSSH private key" deny "-----BEGIN OPENSSH PRIVATE KEY-----"
# synthetic test fixture, not a real key
# trunk-ignore(gitleaks/gcp-api-key)
check_output "Google API key pattern" deny "AIzaSyA1234567890abcdefghijklmnopqrstuv"
check_output "Google OAuth token" deny "ya29.a0AfH6SMBx-example-token-value"
check_output "goog_ prefixed secret" deny "goog_AbCdEfGhIjKlMnOpQr"
check_output "normal command output" clean "total 42\ndrwxr-xr-x 5 user user 4096 Mar 19 10:00 src"
check_output "git log output" clean "abc1234 feat: add new feature"
check_output "Python traceback" clean "Traceback (most recent call last):\n  File \"main.py\""
check_output "JWT token" deny "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"
check_output "AWS access key" deny "AKIAIOSFODNN7EXAMPLE"
check_output "DB connection string" deny "postgres://admin:s3cret@db.example.com:5432/prod"
check_output "service account JSON" deny '{"type": "service_account", "project_id": "test"}'
check_output "GitHub PAT" deny "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmn"
check_output "GitHub fine-grained PAT" deny "github_pat_11AAAAAA0aaaaaaaaaaaaa_BBBBBBBBBBBBBBBBbbbbbbbbbbbbbbbbbbbb0000000000000000000"
check_output "GitHub server token (ghs_)" deny "ghs_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmn"
check_output "GitHub user-to-server (ghu_)" deny "ghu_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmn"
check_output "GitHub OAuth token (gho_)" deny "gho_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmn"
check_output "GitHub refresh token (ghr_)" deny "ghr_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmn"
check_output "PostgreSQL (ql) conn string" deny "postgresql://admin:s3cret@db.example.com:5432/prod"
check_output "MongoDB+SRV conn string" deny "mongodb+srv://admin:s3cret@cluster.example.com/prod"
check_output "MySQL connection string" deny "mysql://admin:s3cret@db.example.com:3306/prod"
check_output "normal base64 (not JWT)" clean "eyJqdXN0IjoiZGF0YSJ9"

# ─── Tool-specific scanning ──────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}PostToolUse: Tool-specific scanning${NC}"

check_output "WebFetch with op://" deny WebFetch "config: op://vault/item/field"
# synthetic test fixture, not a real key
# trunk-ignore(gitleaks/private-key)
check_output "WebSearch with private key" deny WebSearch "-----BEGIN RSA PRIVATE KEY-----"
check_output "WebFetch normal content" clean WebFetch "<html><body>Hello</body></html>"
check_output "Read with op:// in content" deny Read "config: op://vault/item/field"
check_output "Grep with private key match" deny Grep "-----BEGIN RSA PRIVATE KEY-----"
check_output "Read normal file content" clean Read "def hello():\n    return 42"
check_output "Grep normal match" clean Grep "import dagster"

# ─── MCP tool output scanning ────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}PostToolUse: MCP tool output scanning${NC}"

check_output "MCP tool with op://" deny "mcp__bigquery__execute_sql" "op://vault/item/field"
check_output "MCP tool with private key" deny "mcp__dagster__get_run" "-----BEGIN RSA PRIVATE KEY-----"
check_output "MCP tool clean output" clean "mcp__bigquery__execute_sql" "rows_affected: 42"

# ─── High-entropy string boundary (120 chars) ────────────────────────────────
echo ""
echo -e "${YELLOW}PostToolUse: High-entropy string boundary (120 chars)${NC}"

str_119=$(printf 'A%.0s' {1..119})
str_120=$(printf 'A%.0s' {1..120})
str_121=$(printf 'A%.0s' {1..121})
check_output "119-char string (under threshold)" clean "${str_119}"
check_output "120-char string (at threshold)" deny "${str_120}"
check_output "121-char string (over threshold)" deny "${str_121}"

echo ""
echo -e "${YELLOW}PostToolUse: Non-scanned tools${NC}"

check_output "Write tool output not scanned" clean Write "op://vault/item/field"
check_output "Edit tool output not scanned" clean Edit "op://vault/item/field"

# ─── Exit code regression: hooks must exit 0, not 1 ──────────────────────────
# Claude Code treats exit 1 as a non-blocking error (output still shown).
# Only exit 0 with deny JSON on stdout is honored as a block.
echo ""
echo -e "${YELLOW}PostToolUse: Exit code regression (must exit 0 on deny)${NC}"

# trunk-ignore-begin(shellcheck/SC2312): command substitution in function args is intentional
expect_deny_exit0 "PostToolUse JWT deny exits 0" "${OUTPUT_HOOK}" \
  "$(jq -n --arg c 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0' \
    '{tool_name: "Read", tool_output: {content: $c, stdout: $c, stderr: ""}}')"
expect_deny_exit0 "PostToolUse op:// deny exits 0" "${OUTPUT_HOOK}" \
  "$(jq -n --arg c 'config: op://vault/item/field' \
    '{tool_name: "Bash", tool_output: {content: $c, stdout: $c, stderr: ""}}')"
expect_deny_exit0 "PostToolUse high-entropy deny exits 0" "${OUTPUT_HOOK}" \
  "$(jq -n --arg c "$(printf 'A%.0s' {1..120})" \
    '{tool_name: "Bash", tool_output: {content: $c, stdout: $c, stderr: ""}}')"
# trunk-ignore-end(shellcheck/SC2312)

print_summary "Output Scanner"
