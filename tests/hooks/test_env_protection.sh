#!/bin/bash
# Tests for environment variable leakage: printenv, declare, export,
# bare set, os.environ, $VAR expansion allowlist.
#
# Usage: bash tests/hooks/test_env_protection.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tests/hooks/helpers.sh
source "${SCRIPT_DIR}/helpers.sh"

echo ""
echo "========================================="
echo " Env Protection (check-sensitive.sh)"
echo "========================================="

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
# trunk-ignore-begin(shellcheck/SC2016)
expect_deny 'set in $(set) subst' Bash command 'echo $(set)'
expect_deny "set in subshell (set)" Bash command "(set)"
expect_deny "set in backticks" Bash command '`set`'
# trunk-ignore-end(shellcheck/SC2016)

# ─── Pattern 7: Shell variable expansion ────────────────────────────────────
echo ""
echo -e "${YELLOW}Pattern 7: Shell variable expansion${NC}"

# test fixtures: $() must not expand — values are literal command strings for the hook
# trunk-ignore-begin(shellcheck/SC2016)
expect_deny 'echo $SECRET_TOKEN' Bash command 'echo $SECRET_TOKEN'
expect_deny 'echo ${API_KEY}' Bash command 'echo ${API_KEY}'
expect_deny 'echo $GOOGLE_APPLICATION_CREDENTIALS' Bash command 'echo $GOOGLE_APPLICATION_CREDENTIALS'
expect_deny 'echo $DB_PASSWORD' Bash command 'echo $DB_PASSWORD'
expect_deny '${!OP_*} indirect expansion' Bash command 'echo ${!OP_*}'
expect_deny '${!SECRET_*} indirect expansion' Bash command 'echo ${!SECRET_*}'

expect_allow 'echo $HOME (safe var)' Bash command 'echo $HOME'
expect_allow 'echo $PATH (safe var)' Bash command 'echo $PATH'
expect_allow 'echo $DAGSTER_HOME (safe var)' Bash command 'echo $DAGSTER_HOME'
expect_allow 'echo $GOOGLE_CLOUD_PROJECT (safe var)' Bash command 'echo $GOOGLE_CLOUD_PROJECT'
expect_allow 'echo $PWD (safe var)' Bash command 'echo $PWD'
expect_allow 'echo $VIRTUAL_ENV (safe var)' Bash command 'echo $VIRTUAL_ENV'
expect_allow 'echo $UV_LINK_MODE (safe var)' Bash command 'echo $UV_LINK_MODE'
expect_allow 'echo $GITHUB_WORKSPACE (safe var)' Bash command 'echo $GITHUB_WORKSPACE'
# trunk-ignore-end(shellcheck/SC2016)
expect_allow '$? exit code' Bash command 'echo $?'
expect_allow '$# arg count' Bash command 'echo $#'
# trunk-ignore-begin(shellcheck/SC2016)
expect_allow '$@ positional args' Bash command 'echo $@'
expect_allow '$* positional args' Bash command 'echo $*'
expect_allow '$- shell flags' Bash command 'echo $-'
expect_allow '$! background PID' Bash command 'echo $!'
expect_allow '$PYTHONPATH (safe var)' Bash command 'echo $PYTHONPATH'
expect_allow '$RUSTUP_HOME (safe var)' Bash command 'echo $RUSTUP_HOME'
expect_allow '$JAVA_HOME (safe var)' Bash command 'echo $JAVA_HOME'
expect_allow '$CI (safe var)' Bash command 'echo $CI'
expect_allow '$CODESPACES (safe var)' Bash command 'echo $CODESPACES'
expect_allow '${HOME} braced syntax (safe)' Bash command 'echo ${HOME}'
# trunk-ignore-end(shellcheck/SC2016)

print_summary "Env Protection"
