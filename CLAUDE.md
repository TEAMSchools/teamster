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

- **Issue first**: Create a GitHub issue before any planned work — always after
  a brainstorm, before the design doc. Quick fixes do not require one. Use
  `gh issue create`; label with conventional commit type, related source systems
  (e.g., `powerschool`, `deanslist`), and `dagster`/`dbt` when applicable.
  Create the branch with `gh issue develop <number> --name <branch> --checkout`.

- **No commits without a branch**: Never commit to `main` — design docs, specs,
  and code all go on feature branches. Project conventions override skill
  workflows.

- **Branching** (hard gate — complete in order):
  1. **Ask the user: worktree or branch switch?** Do not choose for them.
     - **Worktree** — work in `.worktrees/<branch>`, main workspace stays on
       `main`. No IDE tooling in worktrees. **Edit files directly at
       `.worktrees/<branch>/...` — never edit main workspace and copy over.**
     - **Branch switch** — full IDE support, blocks other branch work.
  2. Create the branch. For worktrees:
     `git worktree add .worktrees/<branch> <branch>` (branch exists from
     `gh issue develop`) or `git worktree add .worktrees/<branch> -b <branch>`
     (no issue).

- **Git**: Commit messages and branch names use
  [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/). Branch
  naming: `<gh-username>/<commit-type>/<brief-description>` (get username from
  `gh api user -q .login`; AI-assisted branches prefix with `claude-`). Prefer
  `git add -u` — naming protected paths triggers the hook, `git add -A` can
  stage unrelated files. Subagents must name specific files in `git add` — never
  `-u`, `-A`, or `.`.

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

- **CLAUDE.md edits**: Default to **not adding**. Only add when the absence
  caused a concrete, repeatable mistake — not a one-off error or something
  already documented elsewhere. Every line competes for context window space.
  Omit human-only context (motivation, rationale, history) — only include what
  changes Claude's behavior in a future session.

## Architecture

This file is a **router** — it contains project-wide conventions, then routes to
subdirectory CLAUDE.md files for domain-specific context. Keep domain-specific
guidance in the nearest subdirectory CLAUDE.md, not here.

**You MUST read the relevant CLAUDE.md file before doing any work in a
subdirectory — reading, explaining, reviewing, or modifying code. Do NOT skip
this step.**
