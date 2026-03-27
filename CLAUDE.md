# CLAUDE.md

## Project Overview

Teamster is a data engineering platform for KIPP TEAM & Family Schools (Newark,
Camden, and Paterson, NJ & Miami, FL) built on **Dagster** (orchestration),
**dbt** (transformations), and **Google BigQuery** (warehouse), with Google
Cloud Storage (GCS) as the intermediate storage layer. Python ≥3.13.

Production runs on **GKE** (Google Kubernetes Engine) via Dagster Cloud.
Development uses **GitHub Codespaces** (devcontainer) — secrets are injected
from 1Password at container start.

## Working Conventions

- **Python execution**: Always `uv run` — never bare `python`, `python3`, or
  venv-installed tools (`dbt`, `dagster`, etc.).

- **Built-in tools over Bash**: Never use Bash for file I/O (read, search, edit,
  write) — use the dedicated tool. No exceptions for convenience, pipes, or
  one-liners. Bash is only for commands with no dedicated tool (`git`, `uv run`,
  `gh`, `docker`, `trunk`, plain `ls`).

- **Docs**: When the user says "docs", they mean the `docs/` folder (MkDocs
  site), not CLAUDE.md files.

- **Verify before claiming**: Do not extrapolate third-party tool behavior from
  general knowledge — read the actual source. Proposed code must match the
  discussion; do not present fixes that contradict what was just agreed on.

- **Git**:
  - Commit messages and branch names use
    [conventional commit](https://www.conventionalcommits.org/en/v1.0.0/) types
    (`feat`, `fix`, `docs`, `refactor`, `chore`, etc.).
  - Branch naming: `<gh-username>/<commit-type>/<brief-description>`. Get the
    username from `gh api user -q .login`. For AI-assisted branches, prefix the
    description with `claude-`.
  - **Staging**: Prefer `git add -u` (no path argument) — naming protected paths
    explicitly triggers the hook, and `git add -A` can stage unrelated files on
    dirty checkouts.
  - **Subagent git staging**: When dispatching subagents, instruct them to name
    specific files in `git add` — never `git add -u`, `git add -A`, or
    `git add .`. Subagents don't know what else is modified in the working tree.

- **GitHub**:
  - **Pull requests**: Squash merge. Use `.github/pull_request_template.md` as
    the PR body — fill in the relevant sections based on the changes.
  - **Issues**: Use `gh issue create` (not the web UI). Label with a
    conventional commit type, any related source systems (e.g., `adp`,
    `powerschool`, `deanslist`), and `dagster` and/or `dbt` when applicable.

- **Branching** (hard gate — complete in order, do not skip steps):
  1. Never commit directly to `main`.
     - This applies even when a skill/plugin instructs you to commit — project
       conventions override skill workflows.
  2. **Create a GitHub issue** if one does not already exist — required after
     brainstorms and for planned work. Quick fixes and small changes do not
     require an issue.
  3. **Ask the user: worktree or branch switch?** Do not choose on their behalf.
     - **Worktree** — work in `.worktrees/<branch>` while main workspace stays
       on `main`. Enables parallel work: compare behavior across branches
       side-by-side, start new tasks without waiting on open PRs, run subagents
       on isolated branches. Downside: IDE tooling stays on the main workspace.
     - **Branch switch** — check out the feature branch in the primary
       workspace. Full IDE support, but blocks other branch work until switch
       back.
  4. Create the branch. When an issue exists, use
     `gh issue develop <number> --name <branch> --checkout`. For worktrees with
     an issue, create the branch first with `gh issue develop`, then
     `git worktree add .worktrees/<branch> <branch>`. Without an issue, use
     `git worktree add .worktrees/<branch> -b <branch>`.

- **Claude CLI**: The binary is provided by the VS Code extension (under
  `~/.vscode-remote/extensions/`) and is not on `$PATH`. It cannot be invoked
  via the Bash tool — the user must run `claude` commands in their terminal.

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
