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

- **Memory vs CLAUDE.md**: Rules and conventions go in CLAUDE.md, not memory.
  Memory is only for non-obvious context not derivable from code (e.g., _why_ a
  surprising design choice was made, user preferences).

- **Built-in tools over Bash**: **Never** use Bash for file I/O — use the
  dedicated tool. No exceptions for convenience, pipes, or one-liners.

  | Bash (NEVER)                       | Tool (ALWAYS)    |
  | ---------------------------------- | ---------------- |
  | `cat`, `head`, `tail`, `less`      | **Read**         |
  | `grep`, `rg`, `ag`, `ack`          | **Grep**         |
  | `find`, `fd`, `ls \| grep`         | **Glob**         |
  | `sed`, `awk`, inline patch scripts | **Edit**         |
  | `echo >`, `cat <<EOF >`, `tee`     | **Write**        |
  | `cp`                               | **Read + Write** |

  Bash is only for commands with no dedicated tool (`git`, `uv run`, `gh`,
  `docker`, `trunk`, plain `ls`).

- **Verify before claiming**: Do not extrapolate third-party tool behavior from
  general knowledge — read the actual source. Proposed code must match the
  discussion; do not present fixes that contradict what was just agreed on.

- **Git**:
  - Commit messages follow
    [conventional commit](https://www.conventionalcommits.org/en/v1.0.0/)
    format.
  - Branch naming: `<gh-username>/<commit-type>/<brief-description>`. Get the
    username from `gh api user -q .login`. For AI-assisted branches, prefix the
    description with `claude-`.
  - **Staging protected paths**: Use bare `git add -u` (no path argument) —
    naming protected paths explicitly (e.g., `git add .claude/settings.json`)
    triggers the hook and gets blocked.

- **GitHub**:
  - **Pull requests**: Squash merge. Use `.github/pull_request_template.md` as
    the PR body — fill in the relevant sections based on the changes.
  - **Issues**: Use `gh issue create` (not the web UI). Label with a
    [conventional commit type](https://www.conventionalcommits.org/en/v1.0.0/)
    (`feat`, `fix`, `docs`, `refactor`, `chore`, etc.), any related source
    systems (e.g., `adp`, `powerschool`, `deanslist`), and `dagster` and/or
    `dbt` when applicable.
  - **Design specs**: Never commit specs to `main`. After a spec is reviewed:
    1. `gh issue create`
    2. `gh issue develop <number> --name <branch> --checkout`
    3. Commit the spec to the new branch and push

- **Claude CLI**: Not on `$PATH` — cannot be run via Bash. Use a terminal.

- **File links in responses**: Use relative paths with no leading slash; bare
  line numbers in anchors with no `L` prefix. Example:
  [.devcontainer/scripts/postCreate.sh:105-109](.devcontainer/scripts/postCreate.sh#105-109)

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
