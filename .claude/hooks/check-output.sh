#!/bin/bash
# PostToolUse hook: scans tool output for patterns that look like leaked secrets.
# Defense-in-depth — catches secrets that slip past the PreToolUse hook.

input=$(cat)
tool_name=$(jq -r '.tool_name' <<<"${input}")

# Scan output from tools that can return sensitive content
[[ ! ${tool_name} =~ ^(Bash|Read|Grep|NotebookEdit|WebFetch|WebSearch|mcp__.*)$ ]] && exit 0

# Extract all string values from tool_response (Claude Code's PostToolUse payload key)
combined=$(jq -r '[.tool_response | .. | strings] | join(" ")' <<<"${input}")

# Attempt to decode and re-scan long base64 strings (catches encoded secrets)
blobs=$(echo "${combined}" | grep -oE '[A-Za-z0-9+/]{40,}={0,2}' || true)
if [[ -n ${blobs} ]]; then
  # trunk-ignore(shellcheck/SC2312): read returns 1 at EOF to terminate the while loop — expected
  decoded=$(echo "${blobs}" | while read -r blob; do
    echo "${blob}" | base64 -d 2>/dev/null || true
  done | tr -d '\0')
  [[ -n ${decoded} ]] && combined="${combined} ${decoded}"
fi

# Look for patterns that indicate secret material in output
# - op:// references (1Password secret URIs)
# - Common secret key prefixes
# - Private key headers
if echo "${combined}" | grep -qiE 'op://|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|PRIVATE KEY-----|AIza[0-9A-Za-z_-]{35}|ya29\.[0-9A-Za-z_-]+|goog_[a-zA-Z0-9_-]+|eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}|ops_eyJ[A-Za-z0-9_-]{50,}|AKIA[0-9A-Z]{16}|(postgres(ql)?|mysql|mongodb(\+srv)?)://[^[:space:]]+:[^[:space:]]+@|"type"[[:space:]]*:[[:space:]]*"service_account"|gh[pusor]_[A-Za-z0-9_]{36,}|github_pat_[A-Za-z0-9_]{22,}'; then
  echo '{"hookSpecificOutput": {"hookEventName": "PostToolUse", "permissionDecision": "deny", "permissionDecisionReason": "⛔ Output contains secret material — blocked"}}'
  exit 0
fi

# Heuristic: block suspiciously long high-entropy strings not already matched
if echo "${combined}" | grep -qE '[A-Za-z0-9+/=_-]{120,}'; then
  echo '{"hookSpecificOutput": {"hookEventName": "PostToolUse", "permissionDecision": "deny", "permissionDecisionReason": "⛔ Output contains high-entropy string — possible encoded secret"}}'
  exit 0
fi
