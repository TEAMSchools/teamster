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

expect_deny "bash referencing hooks" Bash command "cat .claude/hooks/check-sensitive.sh"
expect_deny "bash devcontainer scripts" Bash command "cat .devcontainer/scripts/postCreate.sh"

expect_allow "read settings.json" Read file_path ".claude/settings.json"
expect_allow "read hooks/" Read file_path ".claude/hooks/check-sensitive.sh"
expect_allow "grep in hooks/" Grep path ".claude/hooks/"
expect_allow "read devcontainer scripts" Read file_path ".devcontainer/scripts/postCreate.sh"

# ─── Shell snapshots self-protection ──────────────────────────────────────────
echo ""
echo -e "${YELLOW}Shell snapshots self-protection${NC}"

expect_deny "bash cat shell-snapshots" Bash command "cat /home/vscode/.claude/shell-snapshots/snapshot-bash-123.sh"
expect_allow "read shell-snapshots" Read file_path "/home/vscode/.claude/shell-snapshots/snapshot.sh"
expect_deny "double-slash .claude//hooks/" Bash command "cat .claude//hooks/check-sensitive.sh"

# ─── .git/hooks self-protection ──────────────────────────────────────────────
echo ""
echo -e "${YELLOW}.git/hooks self-protection${NC}"

expect_deny "bash cat .git/hooks/" Bash command "cat .git/hooks/pre-commit"
expect_allow "read .git/hooks/" Read file_path ".git/hooks/pre-commit"
expect_allow "grep in .git/hooks/" Grep path ".git/hooks/"

# ─── .trunk/ config self-protection ──────────────────────────────────────────
echo ""
echo -e "${YELLOW}.trunk/ config self-protection${NC}"

expect_deny "bash cat trunk config" Bash command "cat .trunk/config/.sqlfluff"
expect_allow "read trunk.yaml" Read file_path ".trunk/trunk.yaml"
expect_allow "grep in trunk config" Grep path ".trunk/config/"

# ─── Content mentioning protected paths (should be allowed) ──────────────────
echo ""
echo -e "${YELLOW}Content mentioning protected paths (not accessing them)${NC}"

expect_allow2 "write file whose content mentions .claude/hooks/" Write file_path "docs/CLAUDE.md" content "See .claude/hooks/ for details"
expect_allow2 "write file whose content mentions .trunk/config/" Write file_path "docs/CLAUDE.md" content "SQL rules in .trunk/config/.sqlfluff"
expect_allow2 "write file whose content mentions .devcontainer/scripts/" Write file_path "docs/CLAUDE.md" content "Run .devcontainer/scripts/postCreate.sh"
expect_allow2 "edit file whose new_string mentions .claude/hooks/" Edit file_path "docs/CLAUDE.md" new_string "Read .claude/hooks/check-sensitive.sh"
expect_allow2 "write file whose content mentions .git/hooks/" Write file_path "docs/guide.md" content "Pre-commit runs via .git/hooks/pre-commit"

print_summary "Self-Protection"
