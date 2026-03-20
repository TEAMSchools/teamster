#!/bin/bash
# Tests for hook self-protection: settings, hooks/, shell-snapshots/,
# .devcontainer/scripts/, .git/hooks/, .trunk/ config.
#
# Usage: bash tests/hooks/test_self_protection.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tests/hooks/helpers.sh
source "${SCRIPT_DIR}/helpers.sh"

echo ""
echo "========================================="
echo " Self-Protection (check-sensitive.sh)"
echo "========================================="

# ─── Pattern 2: Hook self-protection ─────────────────────────────────────────
echo ""
echo -e "${YELLOW}Pattern 2: Hook self-protection${NC}"

expect_deny "edit settings.json" Edit file_path ".claude/settings.json"
expect_deny "write to hooks/" Write file_path ".claude/hooks/check-sensitive.sh"
expect_deny "bash referencing hooks" Bash command "cat .claude/hooks/check-sensitive.sh"
expect_deny "edit devcontainer scripts" Edit file_path ".devcontainer/scripts/inject-secrets.sh"
expect_deny "bash devcontainer scripts" Bash command "cat .devcontainer/scripts/postCreate.sh"

expect_allow "read settings.json" Read file_path ".claude/settings.json"
expect_allow "read hooks/" Read file_path ".claude/hooks/check-sensitive.sh"
expect_allow "grep in hooks/" Grep path ".claude/hooks/"
expect_allow "read devcontainer scripts" Read file_path ".devcontainer/scripts/inject-secrets.sh"

# ─── Shell snapshots self-protection ──────────────────────────────────────────
echo ""
echo -e "${YELLOW}Shell snapshots self-protection${NC}"

expect_deny "write to shell-snapshots" Write file_path "/home/vscode/.claude/shell-snapshots/snapshot.sh"
expect_deny "bash cat shell-snapshots" Bash command "cat /home/vscode/.claude/shell-snapshots/snapshot-bash-123.sh"
expect_allow "read shell-snapshots" Read file_path "/home/vscode/.claude/shell-snapshots/snapshot.sh"
expect_deny "double-slash .claude//settings.json" Edit file_path ".claude//settings.json"
expect_deny "double-slash .claude//hooks/" Bash command "cat .claude//hooks/check-sensitive.sh"

# ─── .git/hooks self-protection ──────────────────────────────────────────────
echo ""
echo -e "${YELLOW}.git/hooks self-protection${NC}"

expect_deny "write to .git/hooks/" Write file_path ".git/hooks/pre-commit"
expect_deny "bash cat .git/hooks/" Bash command "cat .git/hooks/pre-commit"
expect_deny "edit .git/hooks/" Edit file_path ".git/hooks/pre-commit"
expect_allow "read .git/hooks/" Read file_path ".git/hooks/pre-commit"
expect_allow "grep in .git/hooks/" Grep path ".git/hooks/"

# ─── .trunk/ config self-protection ──────────────────────────────────────────
echo ""
echo -e "${YELLOW}.trunk/ config self-protection${NC}"

expect_deny "edit trunk.yaml" Edit file_path ".trunk/trunk.yaml"
expect_deny "write to trunk config/" Write file_path ".trunk/config/.sqlfluff"
expect_deny "bash cat trunk config" Bash command "cat .trunk/config/.sqlfluff"
expect_allow "read trunk.yaml" Read file_path ".trunk/trunk.yaml"
expect_allow "grep in trunk config" Grep path ".trunk/config/"

print_summary "Self-Protection"
