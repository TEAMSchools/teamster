#!/bin/bash
# Tests for .claude/hooks/check-sensitive.sh
# Simulates Claude Code PreToolUse hook input and verifies deny/allow behavior.
#
# Usage: bash tests/test_hook_security.sh

set -uo pipefail

HOOK=".claude/hooks/check-sensitive.sh"
PASS=0
FAIL=0
ERRORS=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
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

echo ""
echo "========================================="
echo " Hook Security Tests: check-sensitive.sh"
echo "========================================="

# ─── Pattern 1: Sensitive file/directory patterns ─────────────────────────────
echo ""
echo -e "${YELLOW}Pattern 1: Sensitive file/directory patterns${NC}"

expect_deny ".env file" Bash command "cat .env"
expect_deny ".env in path" Read file_path "/workspaces/teamster/.env"
expect_deny "env/ directory" Read file_path "/workspaces/teamster/env/.env"
expect_deny ".ssh directory" Read file_path "/home/vscode/.ssh/id_rsa"
expect_deny ".pem file" Read file_path "/tmp/server.pem"
expect_deny ".key file" Read file_path "/tmp/private.key"
expect_deny ".cer file" Read file_path "/tmp/cert.cer"
expect_deny "secrets.json" Read file_path "/tmp/secrets.json"
expect_deny "credentials.json" Read file_path "/tmp/credentials.json"
expect_deny "secret-volume" Read file_path "/etc/secret-volume/token"
expect_deny ".devcontainer/tpl/" Read file_path ".devcontainer/tpl/.env.tpl"
expect_deny "glob *.key" Glob pattern "*.key"
expect_deny "glob *.pem" Glob pattern "*.pem"
expect_deny "glob *.cer" Glob pattern "*.cer"

expect_allow "normal Python file" Read file_path "/workspaces/teamster/src/main.py"
expect_allow "normal YAML file" Read file_path "/workspaces/teamster/dbt_project.yml"
expect_allow "glob *.py" Glob pattern "*.py"

# ─── Pattern 2: Hook self-protection ─────────────────────────────────────────
echo ""
echo -e "${YELLOW}Pattern 2: Hook self-protection${NC}"

expect_deny "edit settings.json" Edit file_path ".claude/settings.json"
expect_deny "write to hooks/" Write file_path ".claude/hooks/check-sensitive.sh"
expect_deny "bash referencing hooks" Bash command "cat .claude/hooks/check-sensitive.sh"
expect_deny "edit devcontainer scripts" Edit file_path ".devcontainer/scripts/inject-secrets.sh"
expect_deny "bash devcontainer scripts" Bash command "cat .devcontainer/scripts/postCreate.sh"

expect_allow "read settings.json" Read file_path ".claude/settings.json"
expect_allow "read hooks/" Read file_path ".claude/hooks/check-sensitive.sh"
expect_allow "grep in hooks/" Grep path ".claude/hooks/"
expect_allow "read devcontainer scripts" Read file_path ".devcontainer/scripts/inject-secrets.sh"

# ─── Pattern 3: Environment variable leakage ─────────────────────────────────
echo ""
echo -e "${YELLOW}Pattern 3: Environment variable leakage${NC}"

expect_deny "printenv" Bash command "printenv"
expect_deny "printenv with grep" Bash command "printenv | grep SECRET"
expect_deny "declare -x" Bash command "declare -x"
expect_deny "export -p" Bash command "export -p"
expect_deny "compgen" Bash command "compgen -v"
expect_deny "typeset -x" Bash command "typeset -x"
expect_deny "typeset standalone" Bash command "typeset"
expect_deny "os.environ (Python)" Bash command 'uv run python -c "import os; print(dict(os.environ))"'
expect_deny "os.environ.items()" Bash command 'uv run python -c "import os; [print(f\"{k}={v}\") for k,v in os.environ.items()]"'
expect_deny "/proc/self/environ" Bash command "cat /proc/self/environ"
expect_deny "/proc/1/cmdline" Bash command "cat /proc/1/cmdline"
expect_deny "env command" Bash command "env"
expect_deny "env with grep" Bash command "env | grep TOKEN"

expect_allow "normal python script" Bash command "uv run python src/main.py"
expect_allow "set -e (shell option)" Bash command "set -euo pipefail"
expect_allow "set -o pipefail" Bash command "set -o pipefail"
expect_allow "set +x" Bash command "set +x"
expect_allow "environment word in string" Bash command "echo the environment is ready"

# ─── Pattern 3b: Bare `set` command ──────────────────────────────────────────
echo ""
echo -e "${YELLOW}Pattern 3b: Bare set command${NC}"

expect_deny "set (standalone)" Bash command "set"
expect_deny "set piped to grep" Bash command "set | grep SECRET"
expect_deny "set after semicolon" Bash command "echo hello; set | grep KEY"
expect_deny "set after &&" Bash command "cd /tmp && set | head"
expect_deny "set redirected" Bash command "set > /tmp/vars.txt"

expect_allow "set -e" Bash command "set -e"
expect_allow "set -euo pipefail" Bash command "set -euo pipefail"
expect_allow "set +x" Bash command "set +x"
expect_allow "set -o" Bash command "set -o monitor"
expect_allow "git config set" Bash command "git config set user.name test"
expect_allow "reset command" Bash command "reset"

# ─── Pattern 4: 1Password CLI ────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}Pattern 4: 1Password CLI escalation${NC}"

expect_deny "op vault list" Bash command "op vault list"
expect_deny "op item get" Bash command "op item get 'DB Password'"
expect_deny "op read" Bash command "op read op://vault/item/field"
expect_deny "op document get" Bash command "op document get abc123"
expect_deny "op inject" Bash command "op inject -i template.env"

expect_allow "op --version" Bash command "op --version"
expect_allow "op whoami" Bash command "op whoami"
expect_allow "operation word" Bash command "echo operation complete"

# ─── Pattern 5: Encoding-based bypass ─────────────────────────────────────────
echo ""
echo -e "${YELLOW}Pattern 5: Encoding-based bypass detection${NC}"

expect_deny "base64 -d piped to bash" Bash command 'echo cHJpbnRlbnY= | base64 -d | bash'
expect_deny "base64 -d piped to sh" Bash command 'echo cHJpbnRlbnY= | base64 -d | sh'
expect_deny "xxd piped to bash" Bash command 'echo 7072696e74656e76 | xxd -r -p | bash'
expect_deny "printf hex piped to bash" Bash command 'printf "\x70\x72\x69\x6e\x74\x65\x6e\x76" | bash'
expect_deny "printf hex piped to source" Bash command 'printf "\x70\x72" | source /dev/stdin'

expect_allow "base64 encode (no exec)" Bash command "echo hello | base64"
expect_allow "base64 decode to file" Bash command "base64 -d input.b64 > output.bin"
expect_allow "xxd without pipe to shell" Bash command "xxd file.bin"
expect_allow "printf normal usage" Bash command 'printf "hello %s\n" world'

# ─── Pattern 6: Broad /proc access ───────────────────────────────────────────
echo ""
echo -e "${YELLOW}Pattern 6: Broad /proc access${NC}"

expect_deny "/proc/self/maps" Bash command "cat /proc/self/maps"
expect_deny "/proc/self/status" Bash command "cat /proc/self/status"
expect_deny "/proc/self/mountinfo" Bash command "cat /proc/self/mountinfo"
expect_deny "/proc/1/cgroup" Bash command "cat /proc/1/cgroup"
expect_deny "/proc/self/fd/" Read file_path "/proc/self/fd/0"

expect_allow "/proc reference in string" Bash command "echo check /proc docs"

# ─── Symlink bypass (Pattern 1 + symlink resolution) ─────────────────────────
echo ""
echo -e "${YELLOW}Symlink resolution${NC}"

# Create a temp symlink for testing (clean up after)
TMPLINK="/tmp/test_hook_symlink_$$"
if ln -s /workspaces/teamster/env/.env "${TMPLINK}" 2>/dev/null; then
  expect_deny "symlink to env/.env" Read file_path "${TMPLINK}"
  rm -f "${TMPLINK}"
else
  echo -e "  ${YELLOW}SKIP${NC}: could not create test symlink"
fi

# ─── Cross-cutting: MCP tool coverage ────────────────────────────────────────
echo ""
echo -e "${YELLOW}Cross-cutting: MCP tools respect patterns${NC}"

# MCP tools pass through the same hook now — simulate an MCP tool reading a sensitive path
input_mcp=$(jq -n '{tool_name: "mcp__bigquery__query", tool_input: {command: "SELECT * FROM env/.env"}}')
if echo "${input_mcp}" | bash "${HOOK}" >/dev/null 2>&1; then
  FAIL=$((FAIL + 1))
  ERRORS+="\n  ${RED}FAIL${NC} [should deny]: MCP tool referencing env/ in command"
else
  PASS=$((PASS + 1))
  echo -e "  ${GREEN}PASS${NC} [deny]: MCP tool referencing env/ in command"
fi

# MCP tool with harmless input
input_mcp_ok=$(jq -n '{tool_name: "mcp__bigquery__query", tool_input: {command: "SELECT 1"}}')
if echo "${input_mcp_ok}" | bash "${HOOK}" >/dev/null 2>&1; then
  PASS=$((PASS + 1))
  echo -e "  ${GREEN}PASS${NC} [allow]: MCP tool with harmless query"
else
  FAIL=$((FAIL + 1))
  ERRORS+="\n  ${RED}FAIL${NC} [should allow]: MCP tool with harmless query"
fi

# ─── PostToolUse output scanner ──────────────────────────────────────────────
OUTPUT_HOOK=".claude/hooks/check-output.sh"
if [[ -f ${OUTPUT_HOOK} ]]; then
  echo ""
  echo -e "${YELLOW}PostToolUse: Output scanner (check-output.sh)${NC}"

  check_output() {
    local desc="$1" expect="$2" stdout_val="$3"
    local input
    input=$(jq -n --arg out "${stdout_val}" '{tool_name: "Bash", tool_output: {stdout: $out, stderr: ""}}')
    local result
    result=$(echo "${input}" | bash "${OUTPUT_HOOK}" 2>&1)
    local has_warning=false
    if echo "${result}" | grep -q "warningMessage"; then
      has_warning=true
    fi

    if [[ ${expect} == "warn" && ${has_warning} == "true" ]]; then
      PASS=$((PASS + 1))
      echo -e "  ${GREEN}PASS${NC} [warn]: ${desc}"
    elif [[ ${expect} == "clean" && ${has_warning} == "false" ]]; then
      PASS=$((PASS + 1))
      echo -e "  ${GREEN}PASS${NC} [clean]: ${desc}"
    else
      FAIL=$((FAIL + 1))
      ERRORS+="\n  ${RED}FAIL${NC} [expected ${expect}]: ${desc}"
    fi
  }

  check_output "op:// reference in output" warn "op://vault/item/field"
  # synthetic test fixture, not a real key
  # trunk-ignore(gitleaks/private-key)
  check_output "private key header" warn "-----BEGIN RSA PRIVATE KEY-----"
  check_output "EC private key" warn "-----BEGIN EC PRIVATE KEY-----"
  check_output "OPENSSH private key" warn "-----BEGIN OPENSSH PRIVATE KEY-----"
  # synthetic test fixture, not a real key
  # trunk-ignore(gitleaks/gcp-api-key)
  check_output "Google API key pattern" warn "AIzaSyA1234567890abcdefghijklmnopqrstuv"
  check_output "Google OAuth token" warn "ya29.a0AfH6SMBx-example-token-value"
  check_output "goog_ prefixed secret" warn "goog_AbCdEfGhIjKlMnOpQr"
  check_output "normal command output" clean "total 42\ndrwxr-xr-x 5 user user 4096 Mar 19 10:00 src"
  check_output "git log output" clean "abc1234 feat: add new feature"
  check_output "Python traceback" clean "Traceback (most recent call last):\n  File \"main.py\""
else
  echo ""
  echo -e "  ${YELLOW}SKIP${NC}: ${OUTPUT_HOOK} not found"
fi

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "========================================="
echo -e " Results: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}"
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
