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

# ─── Filesystem MCP write guard (Section 1d) ─────────────────────────────────
# The filesystem MCP's mutating tools are not Bash, so the Bash-only Rule 2
# never fires for them. Section 1d re-applies the protected-path block to those
# tools (write_file/edit_file/move_file/create_directory) so they cannot rewrite
# the enforcement layer. Read-only filesystem tools are intentionally exempt.
echo ""
echo -e "${YELLOW}Filesystem MCP protected-config write guard${NC}"

expect_deny "fs-mcp edit_file settings.json" mcp__filesystem__edit_file path "/workspaces/teamster/.claude/settings.json"
expect_deny "fs-mcp write_file settings.local.json" mcp__filesystem__write_file path "/workspaces/teamster/.claude/settings.local.json"
expect_deny "fs-mcp write_file a hook script" mcp__filesystem__write_file path "/workspaces/teamster/.claude/hooks/check-sensitive.sh"
expect_deny "fs-mcp write_file devcontainer/scripts" mcp__filesystem__write_file path "/workspaces/teamster/.devcontainer/scripts/postCreate.sh"
expect_deny "fs-mcp write_file .trunk/trunk.yaml" mcp__filesystem__write_file path "/workspaces/teamster/.trunk/trunk.yaml"
expect_deny "fs-mcp create_directory .trunk/config" mcp__filesystem__create_directory path "/workspaces/teamster/.trunk/config/x"
expect_deny "fs-mcp write_file shell-snapshots" mcp__filesystem__write_file path "/home/vscode/.claude/shell-snapshots/x.sh"
expect_deny "fs-mcp move_file destination .git/hooks/" mcp__filesystem__move_file destination "/workspaces/teamster/.git/hooks/pre-commit"
expect_deny "fs-mcp move_file source out of hooks/" mcp__filesystem__move_file source "/workspaces/teamster/.claude/hooks/check-sensitive.sh"

# Read-only filesystem-MCP tools may still READ these paths (guard is write-only).
expect_allow "fs-mcp read_text_file settings.json" mcp__filesystem__read_text_file path "/workspaces/teamster/.claude/settings.json"
expect_allow "fs-mcp read_file a hook script" mcp__filesystem__read_file path "/workspaces/teamster/.claude/hooks/check-sensitive.sh"

# Writes elsewhere in the repo are unaffected.
expect_allow "fs-mcp write_file repo source" mcp__filesystem__write_file path "/workspaces/teamster/src/dbt/foo.sql"
expect_allow "fs-mcp write_file .claude/scratch" mcp__filesystem__write_file path "/workspaces/teamster/.claude/scratch/x"
expect_allow "fs-mcp write_file .claude markdown" mcp__filesystem__write_file path "/workspaces/teamster/.claude/FOO.md"

# A file BODY mentioning a protected path must not false-positive (body excluded).
expect_allow2 "fs-mcp write_file body mentions .git/hooks/" mcp__filesystem__write_file path "/workspaces/teamster/src/dbt/foo.sql" content "see .git/hooks/pre-commit"

print_summary "Self-Protection"
