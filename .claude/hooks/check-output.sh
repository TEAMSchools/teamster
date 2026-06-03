#!/bin/bash
# PostToolUse hook: scans tool output for patterns that look like leaked secrets.
# Defense-in-depth — catches secrets that slip past the PreToolUse hook.

input=$(cat)

deny_output() {
  echo '{"hookSpecificOutput": {"hookEventName": "PostToolUse", "permissionDecision": "deny", "permissionDecisionReason": "⛔ Output blocked — unscannable input or secret material"}}'
  exit 0
}

# Fail closed on input this hook cannot understand (empty stdin, unparseable
# JSON, non-object frame, or missing/empty tool_name) — otherwise a nonstandard
# envelope skips scanning entirely and re-opens full passthrough.
if [[ -z ${input} ]] || ! jq -e 'type == "object"' >/dev/null 2>&1 <<<"${input}"; then
  deny_output
fi
tool_name=$(jq -r '.tool_name // ""' <<<"${input}")
# Normalize once: lowercase + strip all whitespace so a re-cased name cannot
# skip the scan gate below (pure parameter expansion — no subshell/pipeline).
tool_name=${tool_name,,}
tool_name=${tool_name//[[:space:]]/}
if [[ -z ${tool_name} ]]; then
  deny_output
fi

# Scan output from tools that can return sensitive content (names normalized)
[[ ! ${tool_name} =~ ^(bash|read|grep|notebookedit|webfetch|websearch|mcp__.*)$ ]] && exit 0

# Extract all string values from tool_response (Claude Code's PostToolUse payload
# key). Fall back to the whole payload when .tool_response is absent so a
# payload-key drift (content under a different key) can't skip scanning (#20).
combined=$(jq -r '[(.tool_response // .) | .. | strings] | join(" ")' <<<"${input}")

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
