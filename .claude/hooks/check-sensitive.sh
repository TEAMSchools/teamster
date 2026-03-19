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

# Normalize: collapse /./ and resolve simple ../ traversals for path fields
normalized=$(echo "${path}" | sed -E 's#/\./#/#g; s#/[^/]+/\.\./#/#g')

# 1. Sensitive file/directory patterns (case-insensitive)
if echo "${normalized}" | grep -qiE '(^|[ /])(\.env|\.ssh|\.pem|\.key|\.cer|secrets\.json|credentials\.json|secret-volume)([ /]|$)|(^|[ /])(\.?/)?env(/|[ ]|$)|\.devcontainer/(tpl|scripts)/|\*\.(cer|key|pem)'; then
  deny
fi

# 2. Hook self-protection — block modifications to hook config (allow reads)
if echo "${normalized}" | grep -qE '\.claude/(settings\.json|settings\.local\.json|hooks/)'; then
  if [[ ${tool_name} == "Read" || ${tool_name} == "Grep" || ${tool_name} == "Glob" ]]; then
    : # allow reads
  elif [[ ${tool_name} == "Bash" ]]; then
    # Only block Bash commands that write to hook config (not mere string mentions)
    if echo "${normalized}" | grep -qE '(>|>>|cp |mv |rm |chmod |sed |awk |tee ).*\.claude/(settings\.json|settings\.local\.json|hooks/)'; then
      deny
    fi
  else
    deny
  fi
fi

# 3. Environment variable / process memory leakage
if echo "${normalized}" | grep -qiE '\bprintenv\b|\bdeclare -x\b|\bset\b|\bcompgen\b|/proc/[^[:space:]]*/environ|/proc/[^[:space:]]*/cmdline|OP_SERVICE_ACCOUNT_TOKEN|OP_SERVICE|ACCOUNT_TOKEN'; then
  deny
fi

# 4. 1Password CLI escalation — prevent using a leaked token to access vault
if echo "${normalized}" | grep -qE '\bop (vault|item|read|document|inject)\b'; then
  deny
fi
