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

# ─── Pattern 1b: Write/Edit content scanning ────────────────────────────────
echo ""
echo -e "${YELLOW}Pattern 1b: Write/Edit content scanning${NC}"

expect_deny2 "Write with os.environ in content" Write file_path "/tmp/x.py" content 'import os; print(dict(os.environ))'
expect_deny2 "Write with printenv in content" Write file_path "/tmp/x.sh" content 'printenv | grep SECRET'
expect_deny2 "Write with .env reference in content" Write file_path "/tmp/x.py" content 'open(".env").read()'
expect_deny2 "Edit with os.environ in new_string" Edit file_path "/tmp/x.py" new_string 'import os; print(os.environ)'
expect_deny2 "Write with op inject in content" Write file_path "/tmp/x.sh" content 'op inject -i template.env'
expect_deny2 "Write with getenv in content" Write file_path "/tmp/x.py" content 'import os; os.getenv("SECRET")'

expect_allow2 "Write normal Python content" Write file_path "/tmp/x.py" content 'print("hello world")'
expect_allow2 "Edit normal content" Edit file_path "/tmp/x.py" new_string 'x = 42'

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
expect_deny "os.getenv() targeted read" Bash command 'uv run python -c "import os; print(os.getenv(\"SECRET\"))"'
expect_deny "os.getenv() with var name" Bash command 'uv run python -c "import os; os.getenv(\"GOOGLE_APPLICATION_CREDENTIALS\")"'
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

expect_deny "base64 two-step via &&" Bash command 'base64 -d payload.b64 > /tmp/x.sh && bash /tmp/x.sh'
expect_deny "base64 two-step via ;" Bash command 'base64 -d payload.b64 > /tmp/x.sh; sh /tmp/x.sh'
expect_deny "xxd two-step via &&" Bash command 'xxd -r -p payload.hex > /tmp/x.sh && bash /tmp/x.sh'

expect_allow "base64 encode (no exec)" Bash command "echo hello | base64"
expect_allow "base64 decode to file" Bash command "base64 -d input.b64 > output.bin"
expect_allow "xxd without pipe to shell" Bash command "xxd file.bin"
expect_allow "printf normal usage" Bash command 'printf "hello %s\n" world'

# ─── Pattern 5a: Process substitution / here-string bypass ───────────────────
echo ""
echo -e "${YELLOW}Pattern 5a: Process substitution / here-string bypass${NC}"

expect_deny "bash <(base64 -d)" Bash command 'bash <(echo cHJpbnRlbnY= | base64 -d)'
expect_deny "sh <(base64 -d)" Bash command 'sh <(echo cHJpbnRlbnY= | base64 -d)'
expect_deny "bash <(xxd)" Bash command 'bash <(echo 7072696e74656e76 | xxd -r -p)'
# test fixture: $() must not expand — value is a literal command string for the hook
# trunk-ignore(shellcheck/SC2016)
expect_deny "bash <<< base64 -d" Bash command 'bash <<< "$(echo cHJpbnRlbnY= | base64 -d)"'
# test fixture: $() must not expand — value is a literal command string for the hook
# trunk-ignore(shellcheck/SC2016)
expect_deny "bash <<< base64 -d (unquoted)" Bash command 'bash <<< $(echo cHJpbnRlbnY= | base64 -d)'

expect_allow "bash <(echo hello)" Bash command 'bash <(echo "echo hello")'

# ─── Pattern 5b: Python runtime string construction ─────────────────────────
echo ""
echo -e "${YELLOW}Pattern 5b: Python runtime string construction${NC}"

expect_deny "python exec+chr construction" Bash command 'uv run python -c "exec(chr(112)+chr(114))"'
expect_deny "python exec+join construction" Bash command "uv run python -c \"exec(''.join(['import',' os']))\""
expect_deny "python exec+bytes construction" Bash command 'uv run python -c "exec(bytes([112,114,105]).decode())"'
expect_deny "exec(base64.b64decode(...))" Bash command 'uv run python -c "import base64; exec(base64.b64decode(b\"cHJpbnRlbnY=\"))"'
expect_deny "exec(codecs.decode(...))" Bash command 'uv run python -c "import codecs; exec(codecs.decode(\"cevagrai\", \"rot13\"))"'
expect_deny "exec(bytes.fromhex(...))" Bash command 'uv run python -c "exec(bytes.fromhex(\"7072696e74656e76\").decode())"'

expect_allow "normal python chr" Bash command 'uv run python -c "print(chr(65))"'
expect_allow "normal python join" Bash command "uv run python -c \"print(','.join(['a','b']))\""
expect_allow "normal python bytes" Bash command 'uv run python -c "print(bytes([65,66]).decode())"'
expect_allow "base64.b64decode without exec" Bash command 'uv run python -c "import base64; print(base64.b64decode(b\"aGVsbG8=\"))"'
expect_allow "codecs.decode without exec" Bash command 'uv run python -c "import codecs; print(codecs.decode(\"uryyb\", \"rot13\"))"'

# ─── Pattern 6: Broad /proc access ───────────────────────────────────────────
echo ""
echo -e "${YELLOW}Pattern 6: Broad /proc access${NC}"

expect_deny "/proc/self/maps" Bash command "cat /proc/self/maps"
expect_deny "/proc/self/status" Bash command "cat /proc/self/status"
expect_deny "/proc/self/mountinfo" Bash command "cat /proc/self/mountinfo"
expect_deny "/proc/1/cgroup" Bash command "cat /proc/1/cgroup"
expect_deny "/proc/self/fd/" Read file_path "/proc/self/fd/0"

expect_allow "/proc reference in string" Bash command "echo check /proc docs"

# ─── Quote/backslash splitting bypass ─────────────────────────────────────────
echo ""
echo -e "${YELLOW}Quote/backslash splitting bypass${NC}"

expect_deny 'pr""intenv (double-quote split)' Bash command 'eval "pr""intenv"'
expect_deny "pr'i'ntenv (single-quote split)" Bash command "pr'i'ntenv"
expect_deny 'pr\intenv (backslash split)' Bash command 'eval pr\\intenv'
expect_deny 'environ with quotes' Bash command 'uv run python -c "import os; print(os.envir\"\"on)"'

# ─── Shell snapshots self-protection ──────────────────────────────────────────
echo ""
echo -e "${YELLOW}Shell snapshots self-protection${NC}"

expect_deny "write to shell-snapshots" Write file_path "/home/vscode/.claude/shell-snapshots/snapshot.sh"
expect_deny "bash cat shell-snapshots" Bash command "cat /home/vscode/.claude/shell-snapshots/snapshot-bash-123.sh"
expect_allow "read shell-snapshots" Read file_path "/home/vscode/.claude/shell-snapshots/snapshot.sh"

# ─── Multi-level path traversal ──────────────────────────────────────────────
echo ""
echo -e "${YELLOW}Multi-level path traversal${NC}"

expect_deny "double ../ to env/" Bash command "cat /workspaces/teamster/src/foo/../../env/.env"
expect_deny "triple ../ to env/" Read file_path "/workspaces/teamster/src/a/b/c/../../../env/.env"

# ─── MCP tool generic field extraction ────────────────────────────────────────
echo ""
echo -e "${YELLOW}MCP tool generic field extraction${NC}"

expect_deny "MCP query field with /proc" "mcp__bigquery__query" query "cat /proc/self/environ"
expect_deny "MCP sql field with .env" "mcp__bigquery__query" sql 'SELECT * FROM read_file(".env")'
expect_deny "MCP command field with env/" "mcp__bigquery__query" command "SELECT * FROM env/.env"
expect_allow "MCP sql field harmless" "mcp__bigquery__query" sql "SELECT 1 AS test"
expect_allow "MCP command field harmless" "mcp__bigquery__query" command "SELECT 1"

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

# ─── PostToolUse output scanner ──────────────────────────────────────────────
OUTPUT_HOOK=".claude/hooks/check-output.sh"
if [[ -f ${OUTPUT_HOOK} ]]; then
  echo ""
  echo -e "${YELLOW}PostToolUse: Output scanner (check-output.sh)${NC}"

  # Unified helper: check_output <desc> <expect> [tool] <content>
  # 3-arg form: check_output "desc" warn|clean "output"        (defaults to Bash)
  # 4-arg form: check_output "desc" warn|clean Tool "output"
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

  echo ""
  echo -e "${YELLOW}PostToolUse: Read/Grep output scanning${NC}"

  check_output "Read with op:// in content" warn Read "config: op://vault/item/field"
  check_output "Grep with private key match" warn Grep "-----BEGIN RSA PRIVATE KEY-----"
  check_output "Read normal file content" clean Read "def hello():\n    return 42"
  check_output "Grep normal match" clean Grep "import dagster"

  # Verify non-Bash/Read/Grep tools are skipped (no warning even with secret content)
  input_skip=$(jq -n '{tool_name: "Write", tool_output: {content: "op://vault/item/field"}}')
  result_skip=$(echo "${input_skip}" | bash "${OUTPUT_HOOK}" 2>&1)
  if echo "${result_skip}" | grep -q "warningMessage"; then
    FAIL=$((FAIL + 1))
    ERRORS+="\n  ${RED}FAIL${NC} [should skip]: Write tool should not be scanned"
  else
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}PASS${NC} [skip]: Write tool output not scanned"
  fi
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
