#!/bin/bash
# PostToolUse hook: scans tool output for patterns that look like leaked secrets.
# Defense-in-depth — catches secrets that slip past the PreToolUse hook.

input=$(cat)
tool_name=$(echo "${input}" | jq -r '.tool_name')

# Scan output from tools that can return sensitive content
[[ ! ${tool_name} =~ ^(Bash|Read|Grep)$ ]] && exit 0

# Extract text from all possible output fields (schema varies by tool)
stdout=$(echo "${input}" | jq -r '.tool_output.stdout // ""')
stderr=$(echo "${input}" | jq -r '.tool_output.stderr // ""')
content=$(echo "${input}" | jq -r '.tool_output.content // ""')
output=$(echo "${input}" | jq -r '.tool_output.output // ""')
combined="${stdout} ${stderr} ${content} ${output}"

# Look for patterns that indicate secret material in output
# - op:// references (1Password secret URIs)
# - Common secret key prefixes
# - Private key headers
if echo "${combined}" | grep -qiE 'op://|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|PRIVATE KEY-----|AIza[0-9A-Za-z_-]{35}|ya29\.[0-9A-Za-z_-]+|goog_[a-zA-Z0-9_-]+|eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}|AKIA[0-9A-Z]{16}|(postgres|mysql|mongodb)://[^[:space:]]+:[^[:space:]]+@|"type"[[:space:]]*:[[:space:]]*"service_account"|gh[ps]_[A-Za-z0-9_]{36,}|github_pat_[A-Za-z0-9_]{22,}'; then
  echo '{"hookSpecificOutput": {"hookEventName": "PostToolUse", "warningMessage": "⚠️  Output may contain secret material — review before sharing"}}'
  exit 0
fi
