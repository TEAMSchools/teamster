#!/bin/bash
# Blocks access to sensitive files and paths.
# Reads tool input as JSON from stdin (provided by Claude Code PreToolUse hooks).
# Scans ALL tool_input string fields to cover arbitrary tool schemas (MCP, etc.).
#
# Limitations: command-string checks are best-effort — bash is Turing-complete
# so obfuscated commands (base64, variable indirection, eval, etc.) cannot be
# caught by regex. Real security boundaries are file permissions (umask 077,
# chmod 700) and 1Password authentication.

deny() {
  echo '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "❌ Cannot access sensitive path"}}'
  exit 1
}

input=$(cat)
tool_name=$(echo "${input}" | jq -r '.tool_name')

# Collect ALL string values from tool_input (covers MCP, NotebookEdit, any tool schema)
# Excludes 'description' (metadata field that could cause false positives)
path=$(echo "${input}" | jq -r '
  [.tool_input | to_entries[] | select(.key != "description") | .value | .. | strings] | join(" ")
')

# Normalize: collapse //, /./, resolve ../ traversals (multi-pass loop), resolve symlinks
normalized=$(echo "${path}" | sed -E ':a; s#//+#/#g; s#/\./#/#g; s#/[^/]+/\.\./#/#g; ta')

# Resolve symlinks on file_path to prevent symlink-based bypass
file_path=$(echo "${input}" | jq -r '.tool_input.file_path // ""')
if [[ -n ${file_path} && -e ${file_path} ]]; then
  resolved=$(readlink -f "${file_path}" 2>/dev/null || echo "${file_path}")
  normalized="${normalized} ${resolved}"
fi

# Strip quotes and backslashes for keyword matching (defeats quote-splitting bypass)
sanitized=${normalized//[\"\'\\]/}

# 1. Sensitive file/directory patterns (case-insensitive)
if echo "${sanitized}" | grep -qiE '(^|[ /])(\.env[.a-z]*|\.ssh|\.pem|\.key|\.cer|secrets\.json|credentials\.json|secret-volume)([ /]|$)|(^|[ /])(\.?/)?env(/|[ ]|$)|\.devcontainer/tpl/|\*?\.(cer|key|pem)([ /]|$)'; then
  deny
fi

# 2. Hook self-protection — block modifications to hook config and shell snapshots (allow reads)
if echo "${sanitized}" | grep -qE '\.claude/(settings\.json|settings\.local\.json|hooks/|shell-snapshots/)|\.devcontainer/scripts/|\.git/hooks/|\.trunk/(trunk\.yaml|config/)'; then
  if [[ ${tool_name} != "Read" && ${tool_name} != "Grep" && ${tool_name} != "Glob" ]]; then
    deny
  fi
fi

# 3. Environment variable / process memory leakage
if echo "${sanitized}" | grep -qiE '\bprintenv\b|\bdeclare -x\b|\bexport -p\b|\bcompgen\b|\btypeset([[:space:]]+-x|\b)|/proc/[^[:space:]]*/environ|/proc/[^[:space:]]*/cmdline|OP_SERVICE_ACCOUNT_TOKEN|OP_SERVICE|ACCOUNT_TOKEN|\benviron\b|\benv\b|\bgetenv\b'; then
  deny
fi

# 3b. Catch `set` as a standalone command (dumps all vars), but not `set -flags`
# trunk-ignore(shellcheck/SC2016): regex contains literal $\( for matching $(set), not a command substitution
if echo "${sanitized}" | grep -qE '(^|[;&|(`][[:space:]]*)set([[:space:]]*$|[[:space:]]*[|>&;)`])|\$\(set([[:space:]]|$|\))'; then
  deny
fi

# 4. 1Password CLI escalation — prevent using a leaked token to access vault
if echo "${sanitized}" | grep -qE '\bop\b.*\b(vault|item|read|document|inject)\b'; then
  deny
fi

# 5. Encoding-based bypass detection (base64/hex piped, chained, or process-substituted)
if echo "${normalized}" | grep -qiE 'base64[[:space:]]+(-d|--decode).*(\||[;&]+).*(bash|sh|source)|\bxxd\b.*(\||[;&]+).*(bash|sh|source)|\bprintf[[:space:]]+.*\\x.*\|.*(bash|sh|source)'; then
  deny
fi

# 5a. Reverse order: bash/sh consuming process substitution or here-string with decode
if echo "${sanitized}" | grep -qiE '\b(bash|sh)\b.*<\(.*base64[[:space:]]+(-d|--decode)|\b(bash|sh)\b.*<<<.*base64[[:space:]]+(-d|--decode)|\b(bash|sh)\b.*<\(.*\bxxd\b'; then
  deny
fi

# 5b. Python runtime string construction (exec/eval with chr/join/bytes/base64/codecs)
if echo "${sanitized}" | grep -qiE '\b(exec|eval)[[:space:]]*\(.*\bchr[[:space:]]*\(|\b(exec|eval)[[:space:]]*\(.*\.join[[:space:]]*\(|\b(exec|eval)[[:space:]]*\(.*\bbytes[[:space:]]*\(|\b(exec|eval)[[:space:]]*\(.*base64\.b64decode|\b(exec|eval)[[:space:]]*\(.*codecs\.decode|\b(exec|eval)[[:space:]]*\(.*\.fromhex'; then
  deny
fi

# 5c. Python __import__ with sensitive modules (bypasses exec() requirement)
if echo "${sanitized}" | grep -qiE '\b__import__[[:space:]]*\(.*\b(os|subprocess|shutil|pty|ctypes|socket|http|urllib|multiprocessing|signal)\b'; then
  deny
fi

# 5d. Python importlib bypass (avoids __import__ check)
if echo "${sanitized}" | grep -qiE '\bimportlib\b.*\b(os|subprocess|shutil|pty|ctypes|socket|http|urllib|multiprocessing|signal)\b'; then
  deny
fi

# 6. Block broad /proc access and /dev/fd/
if echo "${sanitized}" | grep -qE '/proc/[^[:space:]]*/|/dev/fd/'; then
  deny
fi

# 7. Shell variable expansion — block $UPPER_CASE broadly, allowlist known-safe vars
# Block ${!prefix*} (indirect expansion that enumerates variable names)
if echo "${sanitized}" | grep -qE '\$\{![^}]*\}'; then
  deny
fi
# Strip allowed variable references, then deny if any $VAR remain
safe='HOME|PATH|PWD|OLDPWD|USER|SHELL|TERM|LANG|LANGUAGE'
safe+='|LC_[A-Z]+|HOSTNAME|SHLVL|LOGNAME|TZ|TMPDIR|EDITOR|VISUAL|PAGER|DISPLAY'
safe+='|XDG_[A-Z_]+|PS[0-4]|IFS|PPID|UID|EUID|RANDOM|SECONDS|LINENO'
safe+='|OSTYPE|MACHTYPE|HOSTTYPE|BASH_SOURCE|BASH_LINENO|BASH_REMATCH|BASHPID|BASH_VERSION|HISTSIZE|HISTCONTROL|COMP[A-Z_]*'
safe+='|SHELLOPTS|BASHOPTS|DIRSTACK|PIPESTATUS|FUNCNAME|REPLY'
safe+='|DAGSTER_HOME|DBT_PROFILES_DIR|DBT_PROJECT_DIR|DBT_CLOUD_ENVIRONMENT_TYPE|DBT_SEND_ANONYMOUS_USAGE_STATS'
safe+='|GOOGLE_CLOUD_PROJECT|PYTHONDONTWRITEBYTECODE|PYTHONPATH|PYTHONHASHSEED'
safe+='|TRUNK_TELEMETRY|UV_LINK_MODE|UV_RESOLUTION|UV_CACHE_DIR|VIRTUAL_ENV|NVM_DIR'
safe+='|JAVA_HOME|GOPATH|GOROOT|CARGO_HOME|RUSTUP_HOME|NODE_PATH'
safe+='|CI|GITHUB_WORKSPACE|GITHUB_REPOSITORY|GITHUB_REF|GITHUB_SHA|GITHUB_ACTIONS|GITHUB_ACTOR|GITHUB_OUTPUT|GITHUB_EVENT_NAME'
safe+='|CODESPACES|CODESPACE_NAME|REMOTE_CONTAINERS'
stripped=$(echo "${sanitized}" | sed -E "s/\\$\\{?(${safe})\\}?//g")
if echo "${stripped}" | grep -qE '\$\{?[A-Z_][A-Z0-9_]+\}?'; then
  deny
fi

# 8. Block BigQuery write/export operations (data exfiltration prevention)
if [[ ${tool_name} == mcp__bigquery__* ]]; then
  if echo "${sanitized}" | grep -qiE '\bINSERT[[:space:]]+INTO\b|\bUPDATE[[:space:]]+[a-zA-Z`_].*[[:space:]]+SET\b|\bDELETE[[:space:]]+FROM\b|\bMERGE[[:space:]]+INTO\b|\bEXPORT[[:space:]]+DATA\b|\bCREATE[[:space:]]+(OR[[:space:]]+REPLACE[[:space:]]+)?TABLE\b'; then
    deny
  fi
fi
