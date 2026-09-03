# CLAUDE.md

## Never

- **Emit PII values** to any external surface: PR comments, commits, issues,
  Slack, Asana, scheduled-agent output. Redact to `Student A` or column names
  first. Local scratch and the terminal are fine. See _PII reference_.
- **Push to `main`.** Hand a main push to the user; do not retry. Editing and
  committing LOCAL `main` is allowed when the user asks.
- **Run a warehouse `DELETE`/`DROP` or a bulk `launch_multiple_runs`** unless
  the USER's own message names the operation and target ("delete rows where X
  from `dataset.table`"). Draft the statement and have them restate it or run it
  in their terminal. Warehouse DML/DDL always goes to the user's terminal: the
  BigQuery MCP is SELECT-only and `bq` credentials expire mid-session. Splitting
  a bulk launch into per-partition runs to dodge the classifier is not allowed;
  hand a partition-range backfill to the Dagster UI.
- **Touch a worktree through the main-checkout path.** Use `git -C <worktree>`
  and `/workspaces/teamster/.worktrees/<branch>/<path>` on every call.
- **Run bare `python`, `dbt`, or `dagster`.** Always `uv run`.

## Read the nearest CLAUDE.md first

Read the relevant subdirectory CLAUDE.md before any work there (reading,
explaining, reviewing, or modifying). Project-wide conventions live here; domain
specifics live there.

## Before you start

- Before writing a spec or plan: stop and ask the user whether to open a GitHub
  issue first. Do not write until they answer. Not required for quick fixes.
- Before creating a branch: ask worktree or branch switch. For a quick fix, also
  ask whether to anchor with an issue, and honor a decline.
- Before writing any file (spec, code, config): be on the feature branch.
- Opening an issue via `mcp__github__issue_write`: the API applies no template.
  Read `.github/ISSUE_TEMPLATE/bug_report.md` or `feature_request.md` and match
  its structure, plain-language sections first and a "For Claude" fold-out last.
  Label with the conventional-commit type, source systems, and `dagster`/`dbt`
  when applicable.
- IDE selection arrives only in `<ide_selection>` tags. If the user says "this"
  with no selection, ask for the snippet.
- At the investigation-to-build pivot, ask whether to run
  `superpowers:brainstorming`. A design settled in conversation does not waive
  it.
- Before brainstorming a fix for a GitHub issue, re-run its diagnostic (row
  counts, reproduce queries, named files). Issue bodies drift.

## Branches

- Naming: [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/)
  for commits and branches. Branch
  `<gh-username>/<commit-type>/claude-<brief-description>`; username from
  `mcp__github__get_me`.
- With an issue: `gh issue develop <number> --name <branch>` (add `--checkout`
  for a branch switch), then
  `git worktree add /workspaces/teamster/.worktrees/<branch> <branch>`. The path
  must be absolute.
- Without an issue (user declined):
  `git worktree add -b <branch> <abs-path> origin/main` or
  `git checkout -b <branch>`. Name `origin/main`; local `main` is often behind.
- Stacked branch: `gh issue develop <num> --name <branch> --base <parent>`, then
  `git worktree add`. Base other than `main` skips `claude-review`; dbt Cloud CI
  still runs (see `.github/CLAUDE.md`). Unset the upstream right after, per
  `.claude/rules/worktrees.md`.
- Linking an existing remote branch to an issue: `mcp__github__create_branch`
  and GraphQL `createLinkedBranch` both no-op. Deleting the remote branch is
  classifier-blocked even with consent. Create the branch under a NEW name and
  `gh issue develop --name <new-name>`.
- The consent classifier reads only the assistant message before the tool call,
  never `AskUserQuestion` answers. After out-of-band consent
  (`git worktree add -b`, `git checkout -b`, bulk Asana `create_tasks`),
  re-confirm in plain text in the same turn. `gh issue develop --name` fails on
  branch names containing `log`, `auth`, or `secret`: rename and retry.
- Worktree mechanics (paths, cwd, `uv` and dbt invocation, CLAUDE.md
  re-injection) are in `.claude/rules/worktrees.md`, which loads on the first
  read under `.worktrees/`. For Bash-only worktree work, read it first.
- Before resuming a branch, merging `origin/main`, resolving a conflict, or
  diagnosing a CI failure in a file the branch never touched: invoke
  `resuming-a-branch`.

## Git hygiene

- Stage with `git add -u`. Naming protected paths triggers the hook; `-A` stages
  unrelated files.
- A model or column rename sweep includes `*.md`: `--include='*.{sql,yml,md}'`.
  CLAUDE.md examples, specs, and doc cross-refs otherwise go stale.

## Subagents

Dispatch rules, model tiers, and Workflow cleanup inject from
`.claude/context/agent.md` on the first `Agent` or `Workflow` call. Do not
accept a subagent's self-report without the checks there.

## Pull requests and CI

- Squash merge. PR body from `.github/pull_request_template.md`.
- Issue refs (`Refs #N`, `Closes #N`) in the body put the PR on project boards.
  Never `gh project item-add` a PR.
- Invoke `superpowers:receiving-code-review` before processing `claude-review`
  findings, and post a per-finding verdict as a PR comment. Everything else
  about review and CI: invoke `pr-ci-review`.

## Tooling

- One-off deps: `uv run --with <pkg> python script.py`, not `uv add --dev`.
- Credentialed one-offs run under pytest. The autouse session fixture in
  `tests/conftest.py` loads 1Password secrets, so live SFTP/API pulls, asset
  `materialize()`, and `dagster definitions validate` work there. Write a
  throwaway `tests/**/test_zz_*.py`, run `uv run pytest <path> -s`, delete it. A
  plain `uv run python` gets no secrets; do not read that failure as a missing
  credential, and do not call `op` (hook-blocked). See
  [tests/CLAUDE.md](tests/CLAUDE.md).
- Smoke-test the runtime path: call the method against a mock or in a `try`
  block. `hasattr` and `import` pass when an SDK sub-resource is missing.
- Arm the Monitor in the same turn you say you will watch something. An exited
  monitor and a waiting one are both silent.
- Do not truncate or hand off work because the session feels long. The harness
  compacts automatically.
- Before claiming a harness artifact (rewritten output, phantom rendering,
  truncated literal), verify with a derived value: line length, `grep -c`, a
  checksum. A misread is far likelier than a rewriting pipeline.
- On the native VS Code build, Grep and Glob are absent as tools; search with
  `rg`/`grep` via Bash. When the system prompt asks for Bash-first work (auto
  mode), follow it. Otherwise use Read/Edit/Write for file I/O and Bash only for
  `git`, `uv run`, `gh`, `docker`, `trunk`, `ls`.
- Never pipe `Bash(run_in_background=true)` output through `head`/`tail`/`grep`.
  The pipe truncates the output file. Filter afterward.
- After any call that creates or updates a resource with string fields (issue
  title, PR body, commit message), check the returned values match intent.
  Malformed parameters succeed with the wrong payload.
- The Claude CLI is not on `$PATH`. The user runs `claude` commands in their
  terminal.
- Verify third-party tool behavior from source or `--help` before describing it.

## Linting

- Do not run `trunk fmt` or `trunk check` as a routine; the commit and push
  hooks do. But a clean commit hook is not lint-clean. Before pushing SQL, YAML,
  or markdown (specs and plans included), run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the edited checkout. `--force` is required or committed files
  are skipped and markdownlint under-reports.
- Suppress with `trunk-ignore(linter/rule): reason` on the line before the
  flagged line, never linter-native syntax.
- Binary paths, worktree invocation, CI-only markdownlint rules: invoke
  `trunk-lint`.

## Docs

"Docs" means the `docs/` folder (MkDocs), not CLAUDE.md files. "The docs" or
"the reference" means the published page in the `mkdocs.yml` nav, not the specs
and plans under `docs/superpowers/`. When asked whether docs are stale, audit
the published page against shipped code. A stale spec is expected; a wrong
published page is a bug.

## PII reference

`config.meta.contains_pii: true` in model YAML is authoritative but incomplete.
Untagged columns are PII under FERPA's direct-identifier list
([34 CFR §99.3](https://www.ecfr.gov/current/title-34/part-99/section-99.3)):
name, SSN, student/employee ID, address, date/place of birth, mother's maiden
name, biometric record, plus "other information... linked or linkable to a
specific student." Schema mapping: IDs (`student_number`, `employee_number`,
`ssn`, `state_id`, `local_id`, kippadb `school_specific_id`), names (`*_name`),
contact (`email`, `phone`, `address`, `street`, `city`, `zip`),
`dob`/`birth_date`, guardian/parent fields, free-text `comment`/`note` on people
tables, credentials/tokens.

Indirect identifiers (FERPA "linked or linkable"): gender, birth date,
geographic indicators (school, zip), race/ethnicity, religion, place of birth,
education info (grade level, EL status, IEP/504/disability), financial info (FRL
status), activities. Each alone may be safe; combinations may not. When unsure,
consult the [PTAC glossary](https://studentprivacy.ed.gov/glossary) or treat as
PII. Aggregates and deidentified data are not PII.

PII-tagging precedent in staging (powerschool) is narrower than this list: it
omits gender, race/ethnicity, and internal/student ids. For a PII-heavy new
model, confirm scope (direct-only vs direct+indirect) with the user before
tagging.

## Superpowers skill overrides

- Branch creation always goes through _Before you start_ and _Branches_,
  including inside `superpowers:brainstorming` ("Write design doc"),
  `superpowers:writing-plans` ("Save plans to:"), and
  `superpowers:using-git-worktrees`. Pause the skill, run the flow, then write
  specs to `docs/superpowers/specs/...` or plans to `docs/superpowers/plans/...`
  on the new branch.
- `finishing-a-development-branch` / `using-git-worktrees`: this repo uses `uv`,
  not `poetry`/`pip`. Run `uv run dbt build --select <model>+` alongside the
  skills' other tests.
- Ponytail yields to superpowers process skills. It governs the size of what
  gets built inside them, not whether they run.

## Compact Instructions

When summarizing the conversation, always preserve:

- The original task/request verbatim, plus constraints and scope decisions the
  user stated ("don't touch X", "we decided against Y", and why).
- Worktree state: the absolute worktree path, branch name, and which checkout
  (main vs worktree) each pending change lives in; what is committed vs
  uncommitted; open PR/issue numbers.
- Verification state: which tests/builds/lints ran and their results; what is
  verified working vs not yet checked.
- Unresolved items: open questions awaiting the user, known failures not yet
  fixed, and the agreed next step.
- Exact identifiers over descriptions: file paths, model/column names, run IDs,
  verbatim error messages.
- Dead ends already tried, gotchas discovered, and workarounds applied this
  session.

Discard freely: full file contents already on disk, verbose tool output, and
exploration that led nowhere (keep only the conclusion).

## CLAUDE.md Editing Rules

- Before adding a line to any CLAUDE.md: name the specific decision Claude will
  make differently because of it. If you cannot, cut it.
- Where a new line goes: one MCP server's behavior goes in
  `.claude/context/<server>.md` (auto-injected on first use). One directory's
  specifics go in that directory's CLAUDE.md. Worktree mechanics go in
  `.claude/rules/worktrees.md`. Subagent dispatch goes in
  `.claude/context/agent.md`. Conventions scoped by file type or spanning
  directories go in `.claude/rules/<topic>.md` with `paths:` (dbt SQL, dbt YAML,
  Cube models, hooks and settings). Runbooks with no file trigger go in a skill.
  This file keeps only what must be known BEFORE any tool runs: safety
  prohibitions, branch and PR etiquette, and rules whose violation produces a
  silently wrong answer rather than a loud error.
- Bold is reserved for the _Never_ block.

## MCP servers

- Outages: if an MCP tool returns "server disconnected" or an expected tool is
  missing from ToolSearch, surface it to the user before falling back to `gh` or
  BigQuery.
- Subprocess logs:
  `~/.cache/claude-cli-nodejs/-workspaces-teamster/mcp-logs-<name>/<ts>.jsonl`.
  Retries append to the same file; read the newest file's tail. Keys: `debug`,
  `error`.
- Per-server gotchas auto-inject from `.claude/context/<server>.md` on the first
  use of `mcp__<server>__*` (and again after compaction). Edit that file to
  change them.

### Tool selection

- Natural-language analytics questions (students, attendance, grades,
  enrollment, staff): start with `cube`, `meta` then `load`. Cube enforces
  row-level access and PII defaults; raw-warehouse paths bypass them. Query
  shape: [src/cube/CLAUDE.md](src/cube/CLAUDE.md). If
  `dbt:answering-natural-language-questions-with-dbt` auto-loads, do not follow
  it; there is no dbt Semantic Layer here.
- BigQuery MCP: warehouse inspection (raw rows, schema diffs,
  `INFORMATION_SCHEMA`), engineering tasks, and ad-hoc SQL only after
  `cube meta` shows no view covers the columns.
- dbt MCP `show`: only when `ref()`/`source()` resolution is needed.
- GitHub: `mcp__github__*` first. The `gh`-via-Bash list below is an exhaustive
  allowlist; any other `gh` subcommand is forbidden via Bash.
  - `gh issue develop`
  - `gh project item-edit` / `item-add` and `gh api graphql` for ProjectV2
    fields
  - `gh pr checks <n> --json name,bucket,state`
  - `gh run *`, `gh workflow *`, `gh repo edit`
  - `gh api` only to PATCH an existing comment or PR body (`-F body=@<file>`),
    POST a PR review-thread reply, read a file at a pinned SHA with the raw
    Accept header, create/add labels, `-X GET search/issues`

  Mechanics and failure modes: `.claude/context/github.md`.
