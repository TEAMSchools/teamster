#!/bin/bash
# Tests for sensitive file/directory patterns, content scanning,
# quote/backslash bypass, path traversal, and symlink resolution.
#
# Usage: bash tests/hooks/test_sensitive_paths.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tests/hooks/helpers.sh
source "${SCRIPT_DIR}/helpers.sh"

echo ""
echo "========================================="
echo " Sensitive Paths (check-sensitive.sh)"
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

# .kube directory (kubeconfig contains cluster certs and auth tokens)
expect_deny ".kube directory" Read file_path "/home/vscode/.kube/config"
expect_deny ".kube subdirectory" Read file_path "/home/vscode/.kube/cache/discovery"
expect_deny ".kube via Bash" Bash command "cat ~/.kube/config"
expect_deny2 ".kube via Grep" Grep pattern "token" path "/home/vscode/.kube/"

expect_deny ".env.local" Read file_path "/workspaces/teamster/.env.local"
expect_deny ".env.production" Read file_path "/workspaces/teamster/.env.production"
expect_deny ".env.backup" Read file_path "/workspaces/teamster/.env.backup"
expect_deny "glob *.key" Glob pattern "*.key"
expect_deny "glob *.pem" Glob pattern "*.pem"
expect_deny "glob *.cer" Glob pattern "*.cer"

expect_allow "normal Python file" Read file_path "/workspaces/teamster/src/main.py"
expect_allow "normal YAML file" Read file_path "/workspaces/teamster/dbt_project.yml"
expect_allow "glob *.py" Glob pattern "*.py"
expect_deny ".environment (matches .env regex)" Read file_path "/workspaces/teamster/.environment"

# ─── Pattern 1b: Write/Edit content scanning to Pattern 1b: Content is not scanned by Rule 1 (path_only scoping) ────────────────────────────────
echo ""
echo -e "${YELLOW}Pattern 1b: Write/Edit content scanning${NC}"

expect_allow2 "Write with os.environ in content" Write file_path "/tmp/x.py" content 'import os; print(dict(os.environ))'
expect_allow2 "Write with printenv in content (Rule 3 is Bash-only)" Write file_path "/tmp/x.sh" content 'printenv | grep SECRET'
expect_allow2 "Write with .env reference in content" Write file_path "/tmp/x.py" content 'open(".env").read()'
expect_allow2 "Edit with os.environ in new_string" Edit file_path "/tmp/x.py" new_string 'import os; print(os.environ)'
expect_allow2 "Write with op inject in content" Write file_path "/tmp/x.sh" content 'op inject -i template.env'
expect_allow2 "Write with getenv in content (Rule 3 is Bash-only)" Write file_path "/tmp/x.py" content 'import os; os.getenv("SECRET")'

expect_allow2 "Write with op vault (Rule 4 is Bash-only)" Write file_path "/tmp/x.sh" content 'op vault list'

expect_allow2 "Write normal Python content" Write file_path "/tmp/x.py" content 'print("hello world")'
expect_allow2 "Edit normal content" Edit file_path "/tmp/x.py" new_string 'x = 42'

# Confirm docs mentioning sensitive paths are allowed
expect_allow2 "Write docs mentioning secret-volume" Write file_path "/tmp/docs.md" content "Secrets at /etc/secret-volume"
expect_allow2 "Write docs mentioning devcontainer tpl" Write file_path "/tmp/docs.md" content "Templates in .devcontainer/tpl/"
expect_allow2 "Edit new_string mentioning .env" Edit file_path "/tmp/docs.md" new_string "Copy .env.example to .env"

# ─── Quote/backslash splitting bypass ─────────────────────────────────────────
echo ""
echo -e "${YELLOW}Quote/backslash splitting bypass${NC}"

expect_deny 'pr""intenv (double-quote split)' Bash command 'eval "pr""intenv"'
expect_deny "pr'i'ntenv (single-quote split)" Bash command "pr'i'ntenv"
expect_deny 'pr\intenv (backslash split)' Bash command 'eval pr\\intenv'
expect_deny 'environ with quotes' Bash command 'uv run python -c "import os; print(os.envir\"\"on)"'

# ─── Multi-level path traversal ──────────────────────────────────────────────
echo ""
echo -e "${YELLOW}Multi-level path traversal${NC}"

expect_deny "double ../ to env/" Bash command "cat /workspaces/teamster/src/foo/../../env/.env"
expect_deny "triple ../ to env/" Read file_path "/workspaces/teamster/src/a/b/c/../../../env/.env"

# ─── Symlink bypass (Pattern 1 + symlink resolution) ─────────────────────────
echo ""
echo -e "${YELLOW}Symlink resolution${NC}"

# Create a temp symlink for testing (clean up after)
TMPLINK="/tmp/test_hook_symlink_$$"
if ln -s /etc/secret-volume "${TMPLINK}" 2>/dev/null; then
  expect_deny "symlink to secret-volume" Read file_path "${TMPLINK}"
  rm -f "${TMPLINK}"
else
  echo -e "  ${YELLOW}SKIP${NC}: could not create test symlink"
fi

# ─── #1: cert/key files under non-path / MCP keys (Rule 1b scans all leaves) ──
echo ""
echo -e "${YELLOW}#1: cert/key under non-path keys${NC}"

# trunk-ignore-begin(shellcheck/SC2312)
expect_deny_json "MCP uri = .key file" \
  "$(jq -n '{tool_name:"mcp__example__tool", tool_input:{uri:"/tmp/server.key"}}')"
expect_deny_json "MCP nested localPath = .pem file" \
  "$(jq -n '{tool_name:"mcp__example__tool", tool_input:{obj:{localPath:"/home/u/id_rsa.pem"}}}')"
expect_deny_json "MCP source = .cer file" \
  "$(jq -n '{tool_name:"mcp__example__tool", tool_input:{source:"/tmp/chain.cer"}}')"
# content exemption preserved: .key as a code attribute in a Write body allows
expect_allow_json "Write content asset.key (attr, not a file)" \
  "$(jq -n '{tool_name:"Write", tool_input:{file_path:"/tmp/x.py", content:"v = asset.key"}}')"
expect_allow_json "Edit new_string mentioning cert.pem" \
  "$(jq -n '{tool_name:"Edit", tool_input:{file_path:"/tmp/x.py", new_string:"# see cert.pem docs"}}')"
# free-text SQL fields are NOT path-scanned: a dotted column ref must not be
# mistaken for a cert/key file (Rule 1b scans named path keys, not `sql`)
expect_allow_json "BQ sql dot-attr record.key (not a cert file)" \
  "$(jq -n '{tool_name:"mcp__bigquery__execute_sql", tool_input:{sql:"SELECT record.key FROM t"}}')"
expect_allow_json "BQ sql dot-attr a.pem (not a cert file)" \
  "$(jq -n '{tool_name:"mcp__bigquery__execute_sql", tool_input:{sql:"SELECT a.pem FROM t"}}')"
# trunk-ignore-end(shellcheck/SC2312)

# ─── #2: symlink resolution for every path field (not just file_path) ─────────
echo ""
echo -e "${YELLOW}#2: symlink resolution beyond file_path${NC}"

TMPLINK2="/tmp/test_hook_slink_grep_$$"
TMPLINK3="/tmp/test_hook_slink_mcp_$$"
TMPLINK4="/tmp/test_hook_slink_ok_$$"
if ln -s /etc/secret-volume "${TMPLINK2}" 2>/dev/null &&
  ln -s /etc/secret-volume "${TMPLINK3}" 2>/dev/null &&
  ln -s /tmp "${TMPLINK4}" 2>/dev/null; then
  expect_deny2 "Grep path symlink to secret-volume" Grep pattern "x" path "${TMPLINK2}"
  # trunk-ignore-begin(shellcheck/SC2312)
  expect_deny_json "MCP uri symlink to secret-volume" \
    "$(jq -n --arg p "${TMPLINK3}" '{tool_name:"mcp__example__tool", tool_input:{uri:$p}}')"
  # trunk-ignore-end(shellcheck/SC2312)
  expect_allow2 "Grep path symlink to benign /tmp" Grep pattern "x" path "${TMPLINK4}"
  rm -f "${TMPLINK2}" "${TMPLINK3}" "${TMPLINK4}"
else
  echo -e "  ${YELLOW}SKIP${NC}: could not create test symlinks"
fi

# ─── Description field scoping (Agent-only exclusion) ─────────────────────────
echo ""
echo -e "${YELLOW}Description field scoping${NC}"

# trunk-ignore-begin(shellcheck/SC2312)
expect_deny_json "MCP description field with .env" \
  "$(jq -n '{tool_name: "mcp__bigquery__execute_sql", tool_input: {description: "cat .env", sql: "SELECT 1"}}')"

expect_allow_json "Agent description with env word" \
  "$(jq -n '{tool_name: "Agent", tool_input: {description: "check the environment setup", prompt: "list files"}}')"
# trunk-ignore-end(shellcheck/SC2312)

# ─── Bash path protection (retained pending verification gate) ──────
echo ""
echo -e "${YELLOW}Bash path protection (retained pending verification gate)${NC}"

expect_deny "bash cat .env" Bash command "cat .env"
expect_deny "bash cat secret-volume" Bash command "cat /etc/secret-volume/token"
expect_deny "bash cat devcontainer tpl" Bash command "cat .devcontainer/tpl/template"

# ─── Exit code regression: hooks must exit 0, not 1 ──────────────────────────
# Claude Code treats exit 1 as a non-blocking error (tool still executes).
# Only exit 0 with deny JSON on stdout is honored as a block.
echo ""
echo -e "${YELLOW}Exit code regression (PreToolUse must exit 0 on deny)${NC}"

# trunk-ignore-begin(shellcheck/SC2312): command substitution in function args is intentional
expect_deny_exit0 "PreToolUse .env deny exits 0" "${HOOK}" \
  "$(make_input Read file_path /workspaces/teamster/env/.env)"
expect_deny_exit0 "PreToolUse secret-volume deny exits 0" "${HOOK}" \
  "$(make_input Read file_path /etc/secret-volume/token)"
expect_deny_exit0 "PreToolUse bash printenv deny exits 0" "${HOOK}" \
  "$(make_input Bash command printenv)"
# trunk-ignore-end(shellcheck/SC2312)

# ─── #23: additional credential files ───────────────────────────────────────
echo ""
echo -e "${YELLOW}#23: credential files${NC}"

expect_deny "gcloud ADC json" Read file_path "/home/vscode/.config/gcloud/application_default_credentials.json"
expect_deny ".git-credentials" Read file_path "/home/vscode/.git-credentials"
expect_deny ".netrc" Read file_path "/home/vscode/.netrc"
expect_deny "1Password config dir" Read file_path "/home/vscode/.config/op/config"
expect_deny "git-credentials via Bash" Bash command "cat ~/.git-credentials"
expect_deny2 "ADC via Grep" Grep pattern "token" path "/home/vscode/.config/gcloud/application_default_credentials.json"

# controls — lookalike non-credential files stay allowed
expect_allow "normal data.json" Read file_path "/workspaces/teamster/data.json"
expect_allow "netrc substring in a normal name" Read file_path "/workspaces/teamster/src/netrcutils.py"

print_summary "Sensitive Paths"
