#!/bin/bash
# Blocks access to sensitive files and paths.
# Reads tool input as JSON from stdin (provided by Claude Code PreToolUse hooks).
# Covers Read, Edit, Write (file_path) and Bash (command) tools.

input=$(cat)

path=$(echo "${input}" | jq -r '(.tool_input.file_path // "") + " " + (.tool_input.command // "")')

if echo "${path}" | grep -qE '(\.env|\.ssh|secrets\.json|credentials\.json|\.pem|\.key|secret-volume)'; then
  echo '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "❌ Cannot access sensitive path"}}'
  exit 1
fi
