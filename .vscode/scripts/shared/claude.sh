#!/bin/bash
# Sets $CLAUDE to the Claude Code binary path, or empty string if not found.
# trunk-ignore(shellcheck/SC2034): used by sourcing scripts
CLAUDE=$(find ~/.vscode-remote/extensions/anthropic.claude-code-*/resources/native-binary/claude -type f 2>/dev/null | head -1) || true
