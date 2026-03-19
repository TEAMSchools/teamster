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
  [.tool_input | to_entries[] | select(.key != "description") | .value | strings] | join(" ")
')

# Normalize: collapse /./, resolve ../ traversals (multi-pass loop), resolve symlinks
normalized=$(echo "${path}" | sed -E ':a; s#/\./#/#g; s#/[^/]+/\.\./#/#g; ta')

# Resolve symlinks on file_path to prevent symlink-based bypass
file_path=$(echo "${input}" | jq -r '.tool_input.file_path // ""')
if [[ -n ${file_path} && -e ${file_path} ]]; then
  resolved=$(readlink -f "${file_path}" 2>/dev/null || echo "${file_path}")
  normalized="${normalized} ${resolved}"
fi

# Strip quotes and backslashes for keyword matching (defeats quote-splitting bypass)
sanitized=${normalized//[\"\'\\]/}

# 1. Sensitive file/directory patterns (case-insensitive)
if echo "${sanitized}" | grep -qiE '(^|[ /])(\.env|\.ssh|\.pem|\.key|\.cer|secrets\.json|credentials\.json|secret-volume)([ /]|$)|(^|[ /])(\.?/)?env(/|[ ]|$)|\.devcontainer/tpl/|\*?\.(cer|key|pem)([ /]|$)'; then
  deny
fi

# 2. Hook self-protection — block modifications to hook config and shell snapshots (allow reads)
if echo "${sanitized}" | grep -qE '\.claude/(settings\.json|settings\.local\.json|hooks/|shell-snapshots/)|\.devcontainer/scripts/'; then
  if [[ ${tool_name} != "Read" && ${tool_name} != "Grep" && ${tool_name} != "Glob" ]]; then
    deny
  fi
fi

# 3. Environment variable / process memory leakage
if echo "${sanitized}" | grep -qiE '\bprintenv\b|\bdeclare -x\b|\bexport -p\b|\bcompgen\b|\btypeset([[:space:]]+-x|\b)|/proc/[^[:space:]]*/environ|/proc/[^[:space:]]*/cmdline|OP_SERVICE_ACCOUNT_TOKEN|OP_SERVICE|ACCOUNT_TOKEN|\benviron\b|\benv\b|\bgetenv\b'; then
  deny
fi

# 3b. Catch `set` as a standalone command (dumps all vars), but not `set -flags`
if echo "${sanitized}" | grep -qE '(^|[;&|][[:space:]]*)set([[:space:]]*$|[[:space:]]*[|>&])'; then
  deny
fi

# 4. 1Password CLI escalation — prevent using a leaked token to access vault
if echo "${sanitized}" | grep -qE '\bop (vault|item|read|document|inject)\b'; then
  deny
fi

# 5. Encoding-based bypass detection (base64/hex piped, chained, or process-substituted)
if echo "${normalized}" | grep -qiE 'base64[[:space:]]+-d.*(\||[;&]+).*(bash|sh|source)|\bxxd\b.*(\||[;&]+).*(bash|sh|source)|\bprintf[[:space:]]+.*\\x.*\|.*(bash|sh|source)'; then
  deny
fi

# 5a. Reverse order: bash/sh consuming process substitution or here-string with decode
if echo "${sanitized}" | grep -qiE '\b(bash|sh)\b.*<\(.*base64[[:space:]]+-d|\b(bash|sh)\b.*<<<.*base64[[:space:]]+-d|\b(bash|sh)\b.*<\(.*\bxxd\b'; then
  deny
fi

# 5b. Python runtime string construction (exec with chr/join/bytes/base64/codecs)
if echo "${sanitized}" | grep -qiE '\bexec[[:space:]]*\(.*\bchr[[:space:]]*\(|\bexec[[:space:]]*\(.*\.join[[:space:]]*\(|\bexec[[:space:]]*\(.*\bbytes[[:space:]]*\(|\bexec[[:space:]]*\(.*base64\.b64decode|\bexec[[:space:]]*\(.*codecs\.decode|\bexec[[:space:]]*\(.*\.fromhex'; then
  deny
fi

# 6. Block broad /proc access (allow /proc/self/status read-only via exception if needed)
if echo "${sanitized}" | grep -qE '/proc/[^[:space:]]*/'; then
  deny
fi
