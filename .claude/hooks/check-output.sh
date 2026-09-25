#!/bin/bash
# PostToolUse hook: scans tool output for patterns that look like leaked secrets.
# Defense-in-depth — catches secrets that slip past the PreToolUse hook.

input=$(cat)

# PostToolUse ignores hookSpecificOutput.permissionDecision (PreToolUse-only).
# The only way to keep secret material out of the model's context here is
# updatedToolOutput, which REPLACES the tool result. Redact every string leaf of
# tool_response but keep the shape keys `type` and `filePath`: a built-in tool's
# replacement that fails its output schema is silently ignored and the original
# output is shown. additionalContext tells Claude what happened.
emit_redacted() {
	# Payload-key drift (#20): the scan below reads the whole payload when
	# .tool_response is absent, but a replacement built from {} fails the tool's
	# output schema and the harness shows the ORIGINAL. Nothing to redact safely,
	# so fail closed and end the turn instead.
	jq -e 'has("tool_response")' >/dev/null 2>&1 <<<"${input}" || deny_output

	jq -c --arg r "$1" '
    def redact: if type == "object" then with_entries(if (.key | IN("type", "filePath")) then . else .value |= redact end)
      elif type == "array" then map(redact)
      elif type == "string" then "[redacted: secret material]" else . end;
    {hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $r,
      updatedToolOutput: ((.tool_response // {}) | redact)}}' <<<"${input}"
	exit 0
}

deny_output() {
	# Nothing parsable to redact: end the turn with a visible warning instead.
	echo '{"decision": "block", "reason": "⛔ Output blocked — unscannable input or secret material"}'
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
# Image blocks carry the rendered picture as base64 — Read returns
# {type:"image", file:{base64}}, MCP tools {type:"image", data}, the API
# {type:"image", source:{data}} — and any real image trips the 120-char
# heuristic. Drop ONLY that carrier, and only when it is base64-shaped; every
# sibling string (paths, mime types, a plaintext data field) is still scanned.
combined=$(jq -r '
  def is_b64: type == "string" and test("^[A-Za-z0-9+/=[:space:]]+$");
  def carrier(f): (try f catch null) // null;
  def strip_images:
    if type == "object" then
      (if .type == "image" then
         (if (carrier(.file.base64) | is_b64) then del(.file.base64) else . end)
         | (if (carrier(.data) | is_b64) then del(.data) else . end)
         | (if (carrier(.source.data) | is_b64) then del(.source.data) else . end)
       else . end)
      | with_entries(.value |= strip_images)
    elif type == "array" then map(strip_images) else . end;
  [(.tool_response // .) | strip_images | .. | strings] | join(" ")' <<<"${input}")

# Asana pagination cursors: next_page.offset (echoed in next_page.path and .uri)
# is an opaque JWT-shaped token that trips secret_re, jwt_re and the entropy
# heuristic, so a cursor could never be read back to fetch the next page. Exempt
# a token only when it is the offset= query param of an https://app.asana.com/api/
# URL in this same output, then delete that exact token everywhere in the corpus
# (the bare offset field, the path copy). The token charset excludes `/` and
# `:`, so an Asana PAT is never captured; the 16-char floor stops a short value
# from deleting unrelated text. Runs before the decode pass so the cursor's
# base64 segments are not decoded and re-scanned either.
asana_url_re='(^|[^A-Za-z0-9._/:-])https://app\.asana\.com/api/[^[:space:]"<>'"'"']*([?&]|\\u0026)offset=[A-Za-z0-9_.=-]{16,}'
asana_urls=$(echo "${combined}" | grep -oE "${asana_url_re}" || true)
while read -r asana_url; do
	[[ -n ${asana_url} ]] || continue
	cursor=${asana_url##*offset=}
	combined=${combined//"${cursor}"/}
done <<<"${asana_urls}"

# Google Drive pagination cursors: search_files returns nextPageToken, an opaque
# ~!!~-prefixed token (590-790 chars) with no separator break, so the entropy
# heuristic below redacted every multi-page result. Exempt a token only in
# Google Drive MCP output, only as a "nextPageToken" value, and only in the ~!!~
# shape, then delete that exact token from the corpus. Runs before the decode
# pass for the same reason as the Asana cursor above.
if [[ ${tool_name} == mcp__claude_ai_google_drive__* ]]; then
	drive_re='"nextPageToken"[[:space:]]*:[[:space:]]*"(~!!~[A-Za-z0-9_=!~-]{16,})"'
	drive_rest=${combined}
	while [[ ${drive_rest} =~ ${drive_re} ]]; do
		drive_token=${BASH_REMATCH[1]}
		combined=${combined//"${drive_token}"/}
		drive_rest=${drive_rest#*"${drive_token}"}
	done
fi

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
secret_re='op://[^/{}[:space:]]+/|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|PRIVATE KEY-----|AIza[0-9A-Za-z_-]{35}|ya29\.[0-9A-Za-z_-]+|goog_[a-zA-Z0-9_-]+|eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}|ops_eyJ[A-Za-z0-9_-]{50,}|AKIA[0-9A-Z]{16}|(postgres(ql)?|mysql|mongodb(\+srv)?)://[^[:space:]]+:[^[:space:]]+@|"type"[[:space:]]*:[[:space:]]*"service_account"|gh[pusor]_[A-Za-z0-9_]{36,}|github_pat_[A-Za-z0-9_]{22,}|xox[baprs]-[0-9A-Za-z-]{10,}|\b(sk|rk)_(live|test)_[0-9A-Za-z]{16,}|hooks\.slack\.com/services/[A-Za-z0-9/]+|aws_secret_access_key["[:space:]:=]+[A-Za-z0-9/+]{40}'

# Asana PAT: 1/<gid>:<32 hex> (legacy) or 2/<gid>/<gid>:<32 hex>. Mirrored in
# check-sensitive.sh Section 4.
secret_re="${secret_re}"'|\b[12]/[0-9]+(/[0-9]+)?:[0-9a-f]{32}\b'

# On the whitespace-stripped copy scan ONLY the JWT pattern (the realistic
# token-split-across-newline case, #30) — not the full set, which would
# false-positive when stripping merges adjacent lines. Known limitation: a
# Slack/Stripe token split across a newline is not reassembled here.
jwt_re='eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}'
if echo "${combined}" | grep -qiE "${secret_re}" || echo "${stripped}" | grep -qiE "${jwt_re}"; then
	emit_redacted "⛔ Tool output contained secret material — redacted by check-output.sh"
fi

# Heuristic: long high-entropy strings not already matched. Strip base64 image
# data-URIs and ignore pure-hex runs (checksums/hashes) to cut false positives
# (#29) while still catching opaque encoded-secret blobs. A run with no case
# mix is an identifier, path, or hash, not an encoded blob: dot-free dbt paths
# (target/compiled/kipptaf/models/<a>/<b>/tests/dbt_utils_unique_combination_o_<hex>)
# reach 120 chars, while a random 120-char base64 string is single-case with
# p = (38/64)^120 ~ 1e-27. A run with an underscore at least every 24 chars is
# a snake_case identifier: dagster-dbt asset check names embed Title_Case dbt
# column names (135-290 chars, mixed case, a `_` every ~5 chars). Random
# url-safe base64 has a `_` only 1 char in 64: simulated exemption rate 1.6e-4
# at 120 chars, 0 in 200k at 160+. A run with a `_`, `-` or `/` at least every
# 16 chars is a path or slug: GitHub blob URLs for claude-* branches run
# 129-169 chars past `github.com`, mixed case from the org name. Random url-safe
# base64 passes that test at 2e-5 (120 chars), 0 in 200k at 160.
# ponytail: case-mix + separator-spacing tests, not Shannon entropy; an
# entropy floor would stop flagging the 1-bit/char gG fixture in the scanner
# suite, so revisit that fixture before switching.
entropy_input=$(echo "${combined}" | sed -E 's#data:[^,[:space:]]*;base64,[A-Za-z0-9+/=]+##g')
long_runs=$(echo "${entropy_input}" | grep -oE '[A-Za-z0-9+/=_-]{120,}' || true)
if [[ -n ${long_runs} ]] && echo "${long_runs}" | grep -qvE '^[0-9a-fA-F]+$|^[^a-z]*$|^[^A-Z]*$|^([^_]{0,23}_+)*[^_]{0,23}$|^([^_/-]{0,15}[_/-]+)*[^_/-]{0,15}$'; then
	emit_redacted "⛔ Tool output contained a high-entropy string (possible encoded secret) — redacted by check-output.sh"
fi
