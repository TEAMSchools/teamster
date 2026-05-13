# CLAUDE.md

## Layout

```text
src/
  teamster/   # Dagster orchestration code (Python)
  dbt/        # dbt projects, one per warehouse target
tests/        # pytest suites
docs/         # MkDocs site (the "docs" folder; NOT CLAUDE.mds)
.claude/      # Hooks, settings, skills
```

**Read the relevant subdirectory CLAUDE.md before any work there** (reading,
explaining, reviewing, or modifying). Project-wide conventions live in this
file; domain specifics live in the nearest subdirectory CLAUDE.md.

### Subdirectory CLAUDE.mds

| Path                                                                              | Covers                                                                              |
| --------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `src/teamster/CLAUDE.md`                                                          | Dagster code: library/code-location pattern, Python standards, asset key convention |
| `src/teamster/code_locations/<name>/CLAUDE.md`                                    | Per-district specifics (read before touching that location)                         |
| `src/dbt/CLAUDE.md` + `src/dbt/<project>/CLAUDE.md`                               | dbt project conventions per warehouse                                               |
| `src/cube/CLAUDE.md`                                                              | Cube semantic layer: layout, view access policies, `cube.js` security model         |
| `tests/CLAUDE.md`                                                                 | Test layout and fixtures                                                            |
| `.claude/CLAUDE.md`                                                               | Hook protocol, protected paths, scratch dir                                         |
| `.devcontainer/`, `.github/`, `.k8s/`, `.trunk/`, `scripts/`, `docs/` `CLAUDE.md` | Domain-specific operational context                                                 |

## Working Conventions

- **PII stays local.** Never emit PII values (or screenshots/logs containing
  them) to PR comments, commits, issues, Slack, Asana, scheduled-agent outputs,
  or any other external surface. Local artifacts (`.claude/scratch/`,
  `.worktrees/`, terminal) are fine. Before any external write that touched
  values from local validation, replace PII with redacted labels (`Student A`,
  `a sample student`) or column-name references. Aggregates / deidentified ≠
  PII. See _PII reference_ below for what counts.

- **Before writing any spec or plan**: STOP and explicitly ask the user whether
  to open a GitHub issue first. Required for specs/plans; not required for quick
  fixes. Do not write anything until the user answers. If opening: use
  `mcp__github__issue_write`; label with conventional commit type, related
  source systems, and `dagster`/`dbt` when applicable.

- **Before creating a branch**: ask the user — worktree or branch switch? Do not
  choose for them.

- **Before writing any file (spec, code, config)**: be on the feature branch.

- **Worktree**: `gh issue develop <number> --name <branch>` (no `--checkout`),
  then `git worktree add .worktrees/<branch> <branch>`.

- **Linking an existing remote branch to an issue**:
  `mcp__github__create_branch` and GraphQL `createLinkedBranch` both no-op when
  the branch already exists. Delete the remote branch, then
  `gh issue develop <num> --name <branch>`, then re-push local commits.

- **Worktree commands**: Path-flag-driven tools must name the worktree
  explicitly. Use `git -C <worktree>` on every git call (bare `git` from the
  main repo silently commits to `main`) and
  `uv run dbt ... --project-dir <worktree>/src/dbt/<project>` on every dbt call.
  Otherwise prefer absolute paths.

- **Branch switch**: `gh issue develop <number> --name <branch> --checkout`.

- **Git naming**: Commit messages and branch names use
  [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/). Branch
  naming: `<gh-username>/<commit-type>/claude-<brief-description>` (get username
  from `mcp__github__get_me`).

- **Git staging**: Prefer `git add -u` — naming protected paths triggers the
  hook, `git add -A` can stage unrelated files. Subagents must name specific
  files in `git add` — never `-u`, `-A`, or `.`.

- **Dispatching subagents**: Subagents do not auto-invoke skills. In the
  dispatch prompt, name the exact `Skill` tool calls the subagent must run
  before starting work (e.g. `Skill` with
  skill=`dbt:using-dbt-for-analytics-engineering` for a dbt review). For
  negation goals (remove X, no Y), list anti-patterns explicitly — subagents
  otherwise re-introduce familiar idioms (`dbt_utils.deduplicate`,
  `select distinct`, `qualify row_number()=1`).

- **Git resuming**: Before resuming work on an existing branch, merge `main`:
  `git fetch origin main && git merge origin/main`.

- **Pull requests**: Squash merge. Use `.github/pull_request_template.md` as the
  PR body.

- **PR project linkage**: PRs auto-appear on project boards via issue refs
  (`Refs #N`, `Closes #N`) in the body. Do NOT `gh project item-add` a PR.

- **Python**: Always `uv run` — never bare `python`, `python3`, or
  venv-installed tools (`dbt`, `dagster`, etc.).

- **Transient Python deps**: Use `uv run --with <pkg> python script.py` for
  one-off scripts needing a package not in `pyproject.toml` — don't
  `uv add --dev` for throwaway tooling.

- **Built-in tools over Bash**: Use dedicated tools for file I/O (Read, Grep,
  Glob, Edit, Write). Bash is only for commands with no dedicated tool (`git`,
  `uv run`, `gh`, `docker`, `trunk`, `ls`).

- **Don't pipe `Bash(run_in_background=true)` output through
  `head`/`tail`/`grep`**. The pipe truncates what reaches the output file —
  defeats the purpose. Pipe the raw stream; filter with Read/Bash after.

- **Verify tool-call results for resource creation/update**: syntax errors in
  structured tool-call parameters (malformed closing tags, misnested blocks) can
  silently produce corrupted values — the call succeeds without error, just with
  the wrong payload. After any call that creates or updates a resource with
  string fields (issue title, PR body, commit message, etc.), check the returned
  values match intent before moving on.

- **Trunk linting/formatting**: Do not run `trunk fmt` or `trunk check` manually
  — `trunk-fmt-pre-commit` formats at commit time and `trunk-check-pre-push`
  blocks bad pushes, both in the main repo and in worktrees (`core.hooksPath` is
  shared). **Pre-commit hook runs `fmt` only**; sqlfluff/yamllint and other
  check-only linters fire at `pre-push` and in CI. If a session reports "trunk
  clean" on a SQL/YAML change based on commit hooks alone, run
  `.trunk/tools/trunk check --force <files>` to verify before claiming the
  change is lint-clean.

- **Linter**: Use `# trunk-ignore(<linter>/<rule>)` with a reason comment — not
  linter-native disable syntax. Binary:
  `/workspaces/teamster/.trunk/tools/trunk`.

- **Markdown**: Always specify a language on fenced code blocks (MD040). Use
  `text` only when no real language applies.

- **Markdown headings**: increment by one level (markdownlint MD001). `#` title
  goes directly to `##` — never jump to `###`.

- **Claude CLI**: Not on `$PATH` — user must run `claude` commands in their
  terminal, not via Bash tool.

- **Verify third-party tool behavior from source**: Before describing how an MCP
  server, dbt CLI flag, or `gh` subcommand behaves, open the source or run
  `--help` — do not extrapolate from general knowledge.

- **Docs**: "docs" means the `docs/` folder (MkDocs site), not CLAUDE.md files.

### PII reference

`config.meta.contains_pii: true` in model YAML is authoritative but
**incomplete**. Untagged columns are PII under FERPA's direct-identifier list
([34 CFR §99.3](https://www.ecfr.gov/current/title-34/part-99/section-99.3)):
name, SSN, student/employee ID, address, date/place of birth, mother's maiden
name, biometric record, plus "other information... linked or linkable to a
specific student." Schema mapping: IDs (`student_number`, `employee_number`,
`ssn`, `state_id`, `local_id`, kippadb `school_specific_id`), names (`*_name`),
contact (`email`, `phone`, `address`, `street`, `city`, `zip`),
`dob`/`birth_date`, guardian/parent fields, free-text `comment`/`note` on people
tables, credentials/tokens.

Indirect identifiers (combinations covered by FERPA's "linked or linkable"
standard): gender, birth date, geographic indicators (school, zip),
race/ethnicity, religion, place of birth, education info (grade level, EL
status, IEP/504/disability), financial info (FRL status), activities. Each field
alone may be safe; combinations may not. When unsure, consult the
[PTAC glossary](https://studentprivacy.ed.gov/glossary) or treat as PII.

## Superpowers skill overrides

- **Branch creation always goes through the issue-and-branch flow in _Working
  Conventions_** — no exceptions for `superpowers:brainstorming`'s "Write design
  doc" step, `superpowers:writing-plans`' "Save plan" step, or
  `superpowers:using-git-worktrees`' worktree-consent prompt. Pause those
  skills, run the flow, then write specs to `docs/superpowers/specs/...` or
  plans to `docs/superpowers/plans/...` on the new branch. Never
  `git worktree add -b` or `git checkout -b` standalone — the branch must be
  created via `gh issue develop` so it's linked to the issue.

- **`finishing-a-development-branch` verification gate**: Skip the skill's
  `npm test / pytest / ...` heuristic. For dbt changes,
  `uv run dbt build --select <model>+` against the relevant project. For Python
  changes, `uv run pytest` where tests exist. PR body uses
  `.github/pull_request_template.md`.

- **Continuous execution exceptions**: `superpowers:subagent-driven-development`
  and `superpowers:executing-plans` say "do not pause between tasks." Pause
  anyway to ask the user before (a) opening a tracking issue, (b) creating a
  branch or worktree, (c) editing any CLAUDE.md file, (d) modifying protected
  files (hook scripts, `.devcontainer/scripts/`, `.claude/settings*.json`).

## CLAUDE.md Editing Rules

- **Before editing any CLAUDE.md file**: present the proposed change as a quote
  block. Do not apply it until the user approves.

- **CLAUDE.md is for Claude, not humans**: cut motivation, rationale, and
  history written to explain the project to a human reader. Keep them only when
  they measurably change Claude's behavior.

- **Before adding to any CLAUDE.md file**: answer the question: "what specific
  decision or action will Claude make differently because of this line?" If you
  can't name one, cut it.

## MCP Servers

Dagster+ MCP auth: do not revert `.mcp.json` to `op run` —
`OP_SERVICE_ACCOUNT_TOKEN` is scrubbed post-boot, so `op run` silently breaks
after the first Codespace restart. Keep `scripts/dagster-mcp-launch.sh` as the
launcher. Package internals: see
[TEAMSchools/dagster-plus-mcp](https://github.com/TEAMSchools/dagster-plus-mcp).

- **MCP outages**: If an MCP tool returns "server disconnected" or clearly
  impaired responses, surface to the user before working around with raw `gh` /
  BigQuery calls.

### MCP tool selection

For natural-language analytics questions (metrics, KPIs, business-domain
questions about students, attendance, grades, enrollment, staff, etc.), **start
with `cube`** — `meta` to discover views, then `load`. Cube enforces row-level
access policies and PII defaults; raw-warehouse paths bypass them. See
[src/cube/CLAUDE.md](src/cube/CLAUDE.md) for query shape.

**`cube` MCP user email seeding**: The `cube` MCP requires a Google Workspace
email for its JWT security context. Resolution order: `CUBE_USER_EMAIL` env var
→ `~/.config/teamster/cube-user-email` cache file → `ctx.elicit()` prompt →
"missing user email" error directing you to the `set_user_email` tool. In the VS
Code extension (where elicit is silently swallowed), call `set_user_email` with
the email from the `# userEmail` system context block when prompted by the
error.

If `dbt:answering-natural-language-questions-with-dbt` auto-loads, do not follow
it — its dbt-Semantic-Layer path doesn't apply (no dbt SL here) and its
ad-hoc-SQL fallback bypasses Cube's policies. Use the `cube` MCP instead. Fall
back to BigQuery MCP for ad-hoc SQL only after `cube meta` confirms no view
models the needed columns.

Use BigQuery MCP for warehouse-level inspection (raw source rows, schema diffs,
`INFORMATION_SCHEMA`) and for engineering tasks (dbt model validation, audits).

Use dbt MCP's `show` only when `ref()` / `source()` resolution is needed — it
adds compilation overhead.

For run-internal timelines (steps, engine events, failures), use
`mcp__dagster__get_run_logs` — its events are canonical and structured. Note the
unit mismatch: GraphQL `creationTime/startTime/endTime` are float seconds;
`get_run_logs` event `timestamp` is a millisecond string.

GitHub MCP (`mcp__github__*`) is mandatory for any GitHub operation that has an
MCP equivalent. Before running `gh <subcommand>` via Bash, check the
`mcp__github__*` tool list — if a matching tool exists, use it.

`gh` via Bash is permitted only when no MCP equivalent exists. Current cases:

- `gh issue develop` — linked branch creation; `mcp__github__create_branch` does
  not link branches to issues.
- `gh project item-edit --id <ITEM_ID> --project-id <PROJECT_ID> --field-id <FIELD_ID> --single-select-option-id <OPTION_ID>`
  — ProjectV2 field mutations (Status / Tier / Driver / etc.) aren't exposed by
  `mcp__github__*`. To unset a field value (any type), replace the value flag
  with `--clear`. No output on success — verify via `gh api graphql` querying
  the item's `fieldValues`. `gh project item-list` JSON also omits ProjectV2
  custom fields whose names contain spaces (e.g. `PR batch`); single-word custom
  fields (`Driver`, `Tier`, `Status`) do appear. Use the same `fieldValues`
  GraphQL query to read the omitted ones.
- `gh project item-add <PROJECT_NUMBER> --owner <OWNER> --url <ISSUE_URL>` —
  adds an issue/PR to a ProjectV2 board. No `mcp__github__*` equivalent. Combine
  with `gh project item-edit` to set fields after add.
- `gh run *` — Actions run inspection/control; no MCP coverage.
- `gh workflow *` — Actions workflow inspection/dispatch; no MCP coverage.
- `gh repo edit` — repo settings; `gh repo create/view/list` have MCP
  equivalents and are not on this list.
- Editing an existing comment — `mcp__github__add_issue_comment` only creates.
  Use `gh api -X PATCH repos/<owner>/<repo>/issues/comments/<id> -f body='...'`.
- Replying to a PR inline review comment in-thread —
  `mcp__github__add_issue_comment` posts top-level PR comments only, not thread
  replies. Use
  `gh api -X POST repos/<owner>/<repo>/pulls/<pr>/comments/<id>/replies -f body='...'`.

### Dagster asset diagnosis

When verifying failures, fetch the most recent run per job (`list_runs` with
`job_name=..., limit=1`, no status filter) — bulk cross-referencing capped
result sets misses retries and recoveries.

Asset keys do NOT include dbt subdirectory layers (`staging/`, `intermediate/`,
or mart `facts`/`dimensions`/`bridges`) —
`kipptaf/people/int_people__location_crosswalk` (not `.../intermediate/...`) and
`kipptaf/marts/fct_x` (not `kipptaf/facts/fct_x`).

`get_asset_condition_evaluations` paginates with
`cursor=<evaluationId of the oldest record returned>` — not a timestamp or
opaque token.

### Dagster Cloud GraphQL (direct, not via MCP)

Host is `kipptaf.dagster.cloud/<deployment>/graphql` (org is `kipptaf`).
`assetChecksOrError` is nested under `assetNodeOrError`; the evaluation success
field is `success` (not `successful`).

### GKE MCP

Authenticates as impersonated service account
`codespaces@teamster-332318.iam.gserviceaccount.com`. If `PermissionDenied`,
check the `CodespacesRole` custom IAM role, not user IAM bindings.

`mcp__gke__query_logs` uses snake_case keys in `time_range` (`start_time`,
`end_time`), not camelCase. Results cap at 100 — paginate by using the last
entry's timestamp as the next `start_time`. The LQL filter truncates
`time_range` bounds to second precision, so sub-second offsets (e.g.
`...:30.534Z`) are silently rounded down and refetch the same first page. To
page past a sub-second boundary or fetch the tail of a traceback, fall back to
`mcp__gcp-observability__list_log_entries` with `orderBy: "timestamp desc"`.

`query_logs` format templates reject hyphens in dotted key paths
(`{{.labels.k8s-pod/dagster/op}}` fails to parse). Use the Go template `index`
function instead: `{{index .labels "k8s-pod/dagster/op"}}`. Fall back to full
JSON + jq only when nesting is deeper than `index` can express.

For pod-level logs, prefer `mcp__gke__query_logs` over
`mcp__gcp-observability__list_log_entries` — the GKE MCP returns pod labels
(run-id, op, code-location) that the gcp-observability MCP does not.

### GCP Observability MCP

If any tool returns permission denied, flag it to the user — don't assume no
data. `list_time_series` `alignmentPeriod` must end with `s` (e.g., `"60s"` not
`"60"`). Container metrics (`kubernetes.io/container/*`) are keyed by `pod_name`
— no `node_name` label; use `kubernetes.io/node/*` for node-level data.

### BigQuery MCP

Truncates results at 50 rows. When querying `INFORMATION_SCHEMA.COLUMNS` for
wide tables, paginate with `WHERE ordinal_position > N`.

`bq` CLI fallback for shell contexts (Monitor poll loops): binary at
`/usr/local/share/google-cloud-sdk/bin/bq`, `--project_id=teamster-332318`. Same
SELECT-only constraints apply.

Pre-merge queries against PR-branch schema use
`dbt_cloud_pr_<job_definition_id>_<pr_num>_<schema>`. `<job_definition_id>` is
the dbt Cloud CI job ID (stable across runs); read from
`mcp__dbt__get_job_run_details(run_id)` step name
`"Create profile from connection BigQuery (override schema to '...')"`. Prod
`<schema>` lacks unmerged renames.

Chained joins through PR-branch marts (mart-view → mart-view → upstream-view)
hit BigQuery's 16-view nesting limit. Query materialized prod tables instead, or
split the query.

Two BQ query-shape failure modes (not interchangeable):

- `exceeds the maximum allowed number of nested views` — chain depth >16.
  Materialize a mid-chain model.
- `Resources exceeded during query execution: Not enough resources for query planning - query is too complex`
  — fan-out width, can fire well below 16. Materialize the fan-out point.

`INFORMATION_SCHEMA.JOBS.referenced_tables` lists base tables reached via view
expansion, NOT a directly-selected view. To find consumers of a view, filter by
`REGEXP_CONTAINS(query, '<view_name>')`.

For NULL-safe distinct counts on composite keys, use
`count(distinct format("%T|%T", a, b))` — `concat()` returns NULL when any arg
is NULL and silently miscounts violations.

### dbt MCP

Auth via `scripts/dbt-mcp-launch.sh` — do not add `DBT_TOKEN` to `.mcp.json`
directly. `list_jobs` is hard-filtered to `DBT_PROD_ENV_ID`, currently staging
(70403104014899); per-call `environment_id` / `project_id` args exposed by the
schema are ignored. Run-inspection tools (`list_jobs_runs`,
`get_job_run_details`, `get_job_run_error`) ignore env scope and work across
environments by `job_id` / `run_id`. For successful runs, call
`get_job_run_error` with `warning_only=true` to surface test warnings —
status=Success does not mean warning-free.

For job inspection, query Staging env (70403104014899) by job id — Production
env (70403104000025) has no scheduled dbt Cloud jobs.

Job config changes must go through the dbt Cloud UI — no mutation tools exist in
the MCP. Live step logs (`debug_logs`, `structured_logs`) and
`list_job_run_artifacts` return nothing until `artifacts_saved: true` — don't
try to diagnose in-flight runs.
