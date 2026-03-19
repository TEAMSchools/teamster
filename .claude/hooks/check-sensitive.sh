#!/bin/bash
# Blocks access to sensitive files and paths.
# Reads tool input as JSON from stdin (provided by Claude Code PreToolUse hooks).
# Covers Read, Edit, Write (file_path), Bash (command), Grep/Glob (path, pattern) tools.
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

# Collect all fields that may contain paths: file_path, path, command, pattern
path=$(echo "${input}" | jq -r '
  [
    (.tool_input.file_path // ""),
    (.tool_input.path // ""),
    (.tool_input.command // ""),
    (.tool_input.pattern // "")
  ] | map(select(. != "")) | join(" ")
')

# Normalize: collapse /./, resolve simple ../ traversals, resolve symlinks for file_path
normalized=$(echo "${path}" | sed -E 's#/\./#/#g; s#/[^/]+/\.\./#/#g')

# Resolve symlinks on file_path to prevent symlink-based bypass
file_path=$(echo "${input}" | jq -r '.tool_input.file_path // ""')
if [[ -n ${file_path} && -e ${file_path} ]]; then
  resolved=$(readlink -f "${file_path}" 2>/dev/null || echo "${file_path}")
  normalized="${normalized} ${resolved}"
fi

# 1. Sensitive file/directory patterns (case-insensitive)
if echo "${normalized}" | grep -qiE '(^|[ /])(\.env|\.ssh|\.pem|\.key|\.cer|secrets\.json|credentials\.json|secret-volume)([ /]|$)|(^|[ /])(\.?/)?env(/|[ ]|$)|\.devcontainer/tpl/|\*?\.(cer|key|pem)([ /]|$)'; then
  deny
fi

# 2. Hook self-protection — block modifications to hook config (allow reads)
if echo "${normalized}" | grep -qE '\.claude/(settings\.json|settings\.local\.json|hooks/)|\.devcontainer/scripts/'; then
  if [[ ${tool_name} != "Read" && ${tool_name} != "Grep" && ${tool_name} != "Glob" ]]; then
    deny
  fi
fi

# 3. Environment variable / process memory leakage
if echo "${normalized}" | grep -qiE '\bprintenv\b|\bdeclare -x\b|\bexport -p\b|\bcompgen\b|\btypeset([[:space:]]+-x|\b)|/proc/[^[:space:]]*/environ|/proc/[^[:space:]]*/cmdline|OP_SERVICE_ACCOUNT_TOKEN|OP_SERVICE|ACCOUNT_TOKEN|\benviron\b|\benv\b'; then
  deny
fi

# 3b. Catch `set` as a standalone command (dumps all vars), but not `set -flags`
if echo "${normalized}" | grep -qE '(^|[;&|][[:space:]]*)set([[:space:]]*$|[[:space:]]*[|>&])'; then
  deny
fi

# 4. 1Password CLI escalation — prevent using a leaked token to access vault
if echo "${normalized}" | grep -qE '\bop (vault|item|read|document|inject)\b'; then
  deny
fi

# 5. Encoding-based bypass detection (base64/hex piped to execution)
if echo "${normalized}" | grep -qiE 'base64[[:space:]]+-d.*\|.*(bash|sh|source)|\bxxd\b.*\|.*(bash|sh|source)|\bprintf[[:space:]]+.*\\x.*\|.*(bash|sh|source)'; then
  deny
fi

# 6. Block broad /proc access (allow /proc/self/status read-only via exception if needed)
if echo "${normalized}" | grep -qE '/proc/[^[:space:]]*/'; then
  deny
fi
