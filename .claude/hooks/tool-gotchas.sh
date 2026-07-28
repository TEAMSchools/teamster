#!/bin/bash
# PreToolUse hook: injects an MCP server's gotchas the first time that server is
# used in a session, so the guidance is delivered deterministically instead of
# depending on a skill being invoked. Silent (exit 0, no stdout) whenever there
# is nothing to say — this hook never blocks a call.
#
# Content is keyed by MCP server name: mcp__<server>__<tool> reads
# .claude/context/<server>.md. That file IS the configuration — adding a server
# means adding a file, with no edit to this script or to settings.json. A
# missing file makes the hook inert for that server, so sections can be migrated
# out of CLAUDE.md one at a time.
#
# hookEventName is echoed back from the payload because the harness hard-fails
# on a mismatch ("Hook returned incorrect event name"), and so this same script
# works unchanged if the matcher is ever moved to PostToolUse. Note that
# additionalContext is consumed by PreToolUse at runtime but is NOT listed in
# the harness's documented PreToolUse schema — if injection ever stops
# appearing, move this hook to PostToolUse, where the field is documented.

input=$(cat)

# Nothing to do on input this hook cannot understand. Unlike the secret-scanning
# hooks this one fails OPEN: it only adds context, so an unparseable envelope
# must not block the tool call.
if [[ -z ${input} ]] || ! jq -e 'type == "object"' >/dev/null 2>&1 <<<"${input}"; then
  exit 0
fi

tool_name=$(jq -r '.tool_name // ""' <<<"${input}")
event=$(jq -r '.hook_event_name // ""' <<<"${input}")
session=$(jq -r '.session_id // "nosession"' <<<"${input}")

# Only these events consume additionalContext usefully here.
case "${event}" in
PreToolUse | PostToolUse) ;;
*) exit 0 ;;
esac

# mcp__<server>__<tool> -> <server>; anything else is not ours.
case "${tool_name}" in
mcp__*__*) ;;
*) exit 0 ;;
esac
key=${tool_name#mcp__}
key=${key%%__*}

# Defence in depth: the key becomes a path segment, so allow only safe chars.
case "${key}" in
"" | *[!a-zA-Z0-9_-]*) exit 0 ;;
*) ;;
esac

context_file=".claude/context/${key}.md"
if [[ ! -r ${context_file} ]]; then
  exit 0
fi

# Once per session per server.
marker=".claude/scratch/.gotchas-${session}-${key}"
if [[ -e ${marker} ]]; then
  exit 0
fi
mkdir -p .claude/scratch
: >"${marker}"

jq -n --arg ev "${event}" --rawfile body "${context_file}" \
  '{hookSpecificOutput: {hookEventName: $ev, additionalContext: $body}}'
