# CLAUDE.md

## Project Overview

Teamster is a data engineering platform for KIPP TEAM & Family Schools (Newark,
Camden, and Paterson, NJ & Miami, FL) built on **Dagster** (orchestration),
**dbt** (transformations), and **Google BigQuery** (warehouse), with Google
Cloud Storage (GCS) as the intermediate storage layer.

## Working Conventions

- **Python execution**: Always use `uv run` — never bare `python` or `python3`,
  including inline one-liners (`uv run python -c "..."`, not
  `python3 -c "..."`). The project environment is managed by uv.

- **Memory vs CLAUDE.md**: Do not save instructions that should govern every
  session in this project to memory — put them in CLAUDE.md instead. Memory is
  for information not derivable from the codebase or not appropriate for
  CLAUDE.md (e.g., user preferences, one-off context).

- **Built-in tools over Bash**: NEVER use Bash for operations covered by a
  dedicated tool — hooks will reject them. Use Read (not `cat`/`head`/`tail`),
  Grep (not `grep`/`rg`), Glob (not `find`/`ls`), Edit (not `sed`/`awk`), Write
  (not echo redirection). Bash is only for operations that have no dedicated
  tool equivalent.

- **Git**:
  - Do not commit proactively — ask first when a change is complete and tests
    are passing, then commit if confirmed.
  - Commit messages follow
    [conventional commit](https://www.conventionalcommits.org/en/v1.0.0/)
    format. Avoid checkpoint-style messages (`save`, `oops`, `update`, etc.).
  - Branch naming: `<author>/<commit-type>/<brief-description>` (e.g.,
    `cbini/feat/salesforce-alumni-tracking`). For AI-assisted branches, prefix
    the description with `claude-` (e.g.,
    `cbini/feat/claude-salesforce-alumni-tracking`).
  - **Staging protected paths**: Use bare `git add -u` (no path argument) —
    naming protected paths explicitly (e.g., `git add .claude/settings.json`)
    triggers the hook and gets blocked.

- **GitHub**:
  - **Pull requests**: Squash merge. Use `.github/pull_request_template.md` as
    the PR body — fill in the relevant sections based on the changes.
  - **Issues**: Do not open proactively — ask first. Use `gh issue create` (not
    the web UI). Label with a
    [conventional commit type](https://www.conventionalcommits.org/en/v1.0.0/)
    (`feat`, `fix`, `docs`, `refactor`, `chore`, etc.), any related source
    systems (e.g., `adp`, `powerschool`, `deanslist`), and `dagster` and/or
    `dbt` when applicable.
  - **Design specs**: After a spec is written and reviewed:
    1. Open a GitHub issue (`gh issue create`)
    2. Create and link the branch
       (`gh issue develop <number> --name <branch> --checkout`)
    3. Commit the spec to that branch
    4. Push the branch

- **Claude CLI**: The `claude` binary is at
  `~/.vscode-remote/extensions/anthropic.claude-code-*/resources/native-binary/claude`
  and is not on `$PATH`, so it cannot be run via Bash. Run it manually in a
  terminal.

- **Linter**: Use `# trunk-ignore(<linter>/<rule>)` with a reason comment. Do
  not use linter-native disable syntax (e.g., `# shellcheck disable=`, `# noqa`,
  `-- noqa`).

## Architecture

This file is a **router** — it contains project-wide conventions, then routes to
subdirectory CLAUDE.md files for domain-specific context. Keep domain-specific
guidance in the nearest subdirectory CLAUDE.md, not here.

**You MUST read the relevant CLAUDE.md file before doing any work in a
subdirectory — reading, explaining, reviewing, or modifying code. Do NOT skip
this step.**

| Path                      | When                               |
| ------------------------- | ---------------------------------- |
| `src/teamster/CLAUDE.md`  | Dagster code                       |
| `src/dbt/CLAUDE.md`       | dbt models                         |
| `.vscode/CLAUDE.md`       | VS Code tasks/scripts              |
| `.claude/CLAUDE.md`       | hooks, deny rules, protected paths |
| `.devcontainer/CLAUDE.md` | Codespace setup                    |
| `.k8s/CLAUDE.md`          | GKE setup                          |
| `.trunk/CLAUDE.md`        | linting config                     |
| `tests/CLAUDE.md`         | testing                            |
| `scripts/CLAUDE.md`       | project utilities                  |
| `mcp/CLAUDE.md`           | MCP servers/tools                  |
| `docs/CLAUDE.md`          | MkDocs documentation site          |
| Any subdirectory          | that directory's CLAUDE.md         |
