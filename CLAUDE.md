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

- **Before writing any spec or plan**: STOP and explicitly ask the user whether
  to open a GitHub issue first. Required for specs/plans; not required for quick
  fixes. Do not write anything until the user answers. If opening:
  `gh issue create`; label with conventional commit type, related source
  systems, and `dagster`/`dbt` when applicable.

- **Before creating a branch**: ask the user — worktree or branch switch? Do not
  choose for them.

- **Before writing any file (spec, code, config)**: be on the feature branch.

- **Worktree**: `gh issue develop <number> --name <branch>` (no `--checkout`),
  then `git worktree add .worktrees/<branch> <branch>`.

- **Linking an existing remote branch to an issue**:
  `mcp__github__create_branch` and GraphQL `createLinkedBranch` both no-op when
  the branch already exists. Delete the remote branch, then
  `gh issue develop <num> --name <branch>`, then re-push local commits.

- **Worktree git commands**: Always `cd` to the worktree before running `git`
  commands — the main repo and worktree have separate git state. Running
  `git commit` from the main repo commits to `main`, not the worktree branch.

- **Branch switch**: `gh issue develop <number> --name <branch> --checkout`.

- **Git naming**: Commit messages and branch names use
  [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/). Branch
  naming: `<gh-username>/<commit-type>/claude-<brief-description>` (get username
  from `mcp__github__get_me`).

- **Git staging**: Prefer `git add -u` — naming protected paths triggers the
  hook, `git add -A` can stage unrelated files. Subagents must name specific
  files in `git add` — never `-u`, `-A`, or `.`.

- **Git resuming**: Before resuming work on an existing branch, merge `main`:
  `git fetch origin main && git merge origin/main`.

- **Pull requests**: Squash merge. Use `.github/pull_request_template.md` as the
  PR body.

- **Python**: Always `uv run` — never bare `python`, `python3`, or
  venv-installed tools (`dbt`, `dagster`, etc.).

- **Transient Python deps**: Use `uv run --with <pkg> python script.py` for
  one-off scripts needing a package not in `pyproject.toml` — don't
  `uv add --dev` for throwaway tooling.

- **Built-in tools over Bash**: Use dedicated tools for file I/O (Read, Grep,
  Glob, Edit, Write). Bash is only for commands with no dedicated tool (`git`,
  `uv run`, `gh`, `docker`, `trunk`, `ls`).

- **Trunk linting/formatting**: Do not run `trunk fmt` manually — formatting is
  handled by the PostToolUse hook (after Edit/Write) and `trunk-fmt-pre-commit`
  (at commit time). **Before pushing from a worktree**, run
  `/workspaces/teamster/.trunk/tools/trunk check --ci` from the worktree root
  and fix any issues — trunk git hooks are not installed in worktrees.

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

## CLAUDE.md Editing Rules

- **Before editing any CLAUDE.md file**: present the proposed change as a quote
  block with a one-line expected-utility note. Do not apply it until the user
  approves.

- **Before adding to any CLAUDE.md file**: for each line, answer: what specific
  wrong action does this prevent? If you can't name one, cut it. General
  knowledge and human-only context (motivation, rationale, history) don't
  qualify.

## MCP Servers

Dagster+ MCP server: `dagster-plus-mcp` package (`dev` group) —
[TEAMSchools/dagster-plus-mcp](https://github.com/TEAMSchools/dagster-plus-mcp).
See that repo's CLAUDE.md for package internals.

Authenticated via `scripts/dagster-mcp-launch.sh` (reads
`/etc/secret-volume/.op-token`, exchanges for scoped `DAGSTER_CLOUD_API_TOKEN`
via `op read`, execs). Do not revert to `op run` in `.mcp.json` —
`OP_SERVICE_ACCOUNT_TOKEN` is scrubbed post-boot by `postStart.sh`, so `op run`
silently breaks after the first Codespace restart.

### MCP tool selection

Use BigQuery MCP for ad-hoc queries against known production tables. Use dbt
MCP's `show` only when `ref()` / `source()` resolution is needed — it adds
compilation overhead.

### Dagster asset diagnosis

When verifying failures, fetch the most recent run per job (`list_runs` with
`job_name=..., limit=1`, no status filter) — bulk cross-referencing capped
result sets misses retries and recoveries.

### GKE MCP

Authenticates as impersonated service account
`codespaces@teamster-332318.iam.gserviceaccount.com`. If `PermissionDenied`,
check the `CodespacesRole` custom IAM role, not user IAM bindings.

`mcp__gke__query_logs` uses snake_case keys in `time_range` (`start_time`,
`end_time`), not camelCase. Results cap at 100 — paginate by using the last
entry's timestamp as the next `start_time`.

`query_logs` format templates reject hyphens in key names
(`{{.labels.k8s-pod/dagster/op}}` fails). Use full JSON output and extract with
jq instead.

For pod-level logs, prefer `mcp__gke__query_logs` over
`mcp__observability__list_log_entries` — the GKE MCP returns pod labels (run-id,
op, code-location) that the observability MCP does not.

### Observability MCP

If any tool returns permission denied, flag it to the user — don't assume no
data. `list_time_series` `alignmentPeriod` must end with `s` (e.g., `"60s"` not
`"60"`). Container metrics (`kubernetes.io/container/*`) are keyed by `pod_name`
— no `node_name` label; use `kubernetes.io/node/*` for node-level data.

### BigQuery MCP

Truncates results at 50 rows. When querying `INFORMATION_SCHEMA.COLUMNS` for
wide tables, paginate with `WHERE ordinal_position > N`.

Pre-merge queries against PR-branch schema use
`dbt_cloud_pr_<ci_id>_<pr_num>_<schema>` — prod `<schema>` lacks unmerged
renames.

### dbt MCP

Auth via `scripts/dbt-mcp-launch.sh` — do not add `DBT_TOKEN` to `.mcp.json`
directly. `list_jobs` is hard-filtered to `DBT_PROD_ENV_ID`, currently staging
(70403104014899); per-call `environment_id` / `project_id` args exposed by the
schema are ignored. Run-inspection tools (`list_jobs_runs`,
`get_job_run_details`, `get_job_run_error`) ignore env scope and work across
environments by `job_id` / `run_id`. For successful runs, call
`get_job_run_error` with `warning_only=true` to surface test warnings —
status=Success does not mean warning-free.
