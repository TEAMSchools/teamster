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
[[ ! ${tool_name} =~ ^(bash|read|grep|glob|notebookedit|webfetch|websearch|mcp__.*)$ ]] && exit 0

# Extract all string values from tool_response (Claude Code's PostToolUse payload
# key). Fall back to the whole payload when .tool_response is absent so a
# payload-key drift (content under a different key) can't skip scanning (#20).
combined=$(jq -r '[(.tool_response // .) | .. | strings] | join(" ")' <<<"${input}")

# Decode candidate blobs and re-scan (catches encoded secrets). Two explicit
# passes — standard base64 and url-safe base64 (#16) — so path separators aren't
# conflated with the alphabet. Floor 24 covers real token formats (128-bit key =
# 22+ chars, JWT header = 24+) while avoiding decode noise from short ids (#17).
# Each blob is also base64-then-gunzip decoded (#18), size-capped to 64 KB so a
# gzip bomb can't exhaust memory.
std_blobs=$(echo "${combined}" | grep -oE '[A-Za-z0-9+/]{24,}={0,2}' || true)
url_blobs=$(echo "${combined}" | grep -oE '[A-Za-z0-9_-]{24,}' || true)
if [[ -n ${std_blobs} || -n ${url_blobs} ]]; then
  # tr '_-' '/+' is a no-op on standard blobs and normalizes url-safe ones.
  # trunk-ignore(shellcheck/SC2312): read returns 1 at EOF to terminate the loop — expected
  decoded=$(printf '%s\n%s\n' "${std_blobs}" "${url_blobs}" | while read -r blob; do
    printf '%s' "${blob}" | tr '_-' '/+' | base64 -d 2>/dev/null || true
  done | tr -d '\0')
  [[ -n ${decoded} ]] && combined="${combined} ${decoded}"
  # trunk-ignore(shellcheck/SC2312): read returns 1 at EOF to terminate the loop — expected
  inflated=$(printf '%s\n%s\n' "${std_blobs}" "${url_blobs}" | while read -r blob; do
    printf '%s' "${blob}" | tr '_-' '/+' | base64 -d 2>/dev/null | gunzip -c 2>/dev/null | head -c 65536 || true
  done | tr -d '\0')
  [[ -n ${inflated} ]] && combined="${combined} ${inflated}"
fi

# Whitespace-stripped copy catches a token split across newlines/spaces (#30).
stripped=${combined//[[:space:]]/}

# Named secret patterns. Mirrors check-sensitive.sh Section 4 — update BOTH if
# adding a token type. Adds (Batch 6, #19): Slack (xox*), Stripe (sk/rk_live),
# Slack webhook, and contextual aws_secret_access_key. A generic
# key/secret/token=<value> rule was trialed but BACKED OUT — it false-positived
# on doc placeholders (e.g. "password: enter-your-password-here"); the
# high-entropy heuristic below still catches opaque values.
secret_re='op://|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|PRIVATE KEY-----|AIza[0-9A-Za-z_-]{35}|ya29\.[0-9A-Za-z_-]+|goog_[a-zA-Z0-9_-]+|eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}|ops_eyJ[A-Za-z0-9_-]{50,}|AKIA[0-9A-Z]{16}|(postgres(ql)?|mysql|mongodb(\+srv)?)://[^[:space:]]+:[^[:space:]]+@|"type"[[:space:]]*:[[:space:]]*"service_account"|gh[pusor]_[A-Za-z0-9_]{36,}|github_pat_[A-Za-z0-9_]{22,}|xox[baprs]-[0-9A-Za-z-]{10,}|\b(sk|rk)_(live|test)_[0-9A-Za-z]{16,}|hooks\.slack\.com/services/[A-Za-z0-9/]+|aws_secret_access_key["[:space:]:=]+[A-Za-z0-9/+]{40}'

# On the whitespace-stripped copy scan ONLY the JWT pattern (the realistic
# token-split-across-newline case, #30) — not the full set, which would
# false-positive when stripping merges adjacent lines. Known limitation: a
# Slack/Stripe token split across a newline is not reassembled here.
jwt_re='eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}'
if echo "${combined}" | grep -qiE "${secret_re}" || echo "${stripped}" | grep -qiE "${jwt_re}"; then
  echo '{"hookSpecificOutput": {"hookEventName": "PostToolUse", "permissionDecision": "deny", "permissionDecisionReason": "⛔ Output contains secret material — blocked"}}'
  exit 0
fi

# Heuristic: long high-entropy strings not already matched. Strip base64 image
# data-URIs and ignore pure-hex runs (checksums/hashes) to cut false positives
# (#29) while still catching opaque encoded-secret blobs.
entropy_input=$(echo "${combined}" | sed -E 's#data:[^,[:space:]]*;base64,[A-Za-z0-9+/=]+##g')
long_runs=$(echo "${entropy_input}" | grep -oE '[A-Za-z0-9+/=_-]{120,}' || true)
if [[ -n ${long_runs} ]] && echo "${long_runs}" | grep -qvE '^[0-9a-fA-F]+$'; then
  echo '{"hookSpecificOutput": {"hookEventName": "PostToolUse", "permissionDecision": "deny", "permissionDecisionReason": "⛔ Output contains high-entropy string — possible encoded secret"}}'
  exit 0
fi
