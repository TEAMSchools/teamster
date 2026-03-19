#!/bin/bash
# PostToolUse hook: scans Bash tool output for patterns that look like leaked secrets.
# Defense-in-depth — catches secrets that slip past the PreToolUse hook.

input=$(cat)
tool_name=$(echo "${input}" | jq -r '.tool_name')

# Only scan Bash output
[[ ${tool_name} != "Bash" ]] && exit 0

stdout=$(echo "${input}" | jq -r '.tool_output.stdout // ""')
stderr=$(echo "${input}" | jq -r '.tool_output.stderr // ""')
combined="${stdout} ${stderr}"

# Look for patterns that indicate secret material in output
# - op:// references (1Password secret URIs)
# - Common secret key prefixes
# - Private key headers
if echo "${combined}" | grep -qiE 'op://|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|PRIVATE KEY-----|AIza[0-9A-Za-z_-]{35}|ya29\.[0-9A-Za-z_-]+|goog_[a-zA-Z0-9_-]+'; then
  echo '{"hookSpecificOutput": {"hookEventName": "PostToolUse", "warningMessage": "⚠️  Output may contain secret material — review before sharing"}}'
  exit 0
fi
