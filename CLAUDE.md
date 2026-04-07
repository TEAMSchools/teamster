# CLAUDE.md

## Project Overview

Teamster is a data engineering platform for KIPP TEAM & Family Schools (Newark,
Camden, and Paterson, NJ & Miami, FL) built on **Dagster** (orchestration),
**dbt** (transformations), and **Google BigQuery** (warehouse), with Google
Cloud Storage (GCS) as the intermediate storage layer. Python ≥3.13.

Production runs on **GKE** (Google Kubernetes Engine) via Dagster Cloud.
Development uses **GitHub Codespaces** (devcontainer) — secrets are injected
from 1Password at container start.

## Architecture

This file is a **router** — it contains project-wide conventions, then routes to
subdirectory CLAUDE.md files for domain-specific context. Keep domain-specific
guidance in the nearest subdirectory CLAUDE.md, not here.

**You MUST read the relevant CLAUDE.md file before doing any work in a
subdirectory — reading, explaining, reviewing, or modifying code. Do NOT skip
this step.**

## Working Conventions

- **Before writing any spec or plan**: create a GitHub issue (`gh issue create`;
  label with conventional commit type, related source systems, and
  `dagster`/`dbt` when applicable). Quick fixes do not require one.

- **Before creating a branch**: ask the user — worktree or branch switch? Do not
  choose for them.

- **Before writing any file (spec, code, config)**: be on the feature branch.

- **Worktree**: `gh issue develop <number> --name <branch>` (no `--checkout`),
  then `git worktree add .worktrees/<branch> <branch>`.

- **Branch switch**: `gh issue develop <number> --name <branch> --checkout`.

- **Git naming**: Commit messages and branch names use
  [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/). Branch
  naming: `<gh-username>/<commit-type>/claude-<brief-description>` (get username
  from `gh api user -q .login`).

- **Git staging**: Prefer `git add -u` — naming protected paths triggers the
  hook, `git add -A` can stage unrelated files. Subagents must name specific
  files in `git add` — never `-u`, `-A`, or `.`.

- **Git resuming**: Before resuming work on an existing branch, merge `main`:
  `git fetch origin main && git merge origin/main`.

- **Pull requests**: Squash merge. Use `.github/pull_request_template.md` as the
  PR body.

- **Python**: Always `uv run` — never bare `python`, `python3`, or
  venv-installed tools (`dbt`, `dagster`, etc.).

- **Built-in tools over Bash**: Use dedicated tools for file I/O (Read, Grep,
  Glob, Edit, Write). Bash is only for commands with no dedicated tool (`git`,
  `uv run`, `gh`, `docker`, `trunk`, `ls`).

- **Linter**: Use `# trunk-ignore(<linter>/<rule>)` with a reason comment — not
  linter-native disable syntax. Binary:
  `/workspaces/teamster/.trunk/tools/trunk`.

- **Markdown**: Always specify a language on fenced code blocks (MD040). Use
  `text` only when no real language applies.

- **Claude CLI**: Not on `$PATH` — user must run `claude` commands in their
  terminal, not via Bash tool.

- **Verify before claiming**: Read actual source code — do not extrapolate
  third-party tool behavior from general knowledge.

- **Docs**: "docs" means the `docs/` folder (MkDocs site), not CLAUDE.md files.

- **Before editing any CLAUDE.md file**: present the proposed change as a quote
  block with a one-line expected-utility note. Do not apply it until the user
  approves.

- **Before adding to any CLAUDE.md file**: verify the addition changes Claude's
  behavior. Do not add human-only context (motivation, rationale, history).
