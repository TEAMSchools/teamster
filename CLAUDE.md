# CLAUDE.md

## Layout

**Read the relevant subdirectory CLAUDE.md before any work there** (reading,
explaining, reviewing, or modifying). Project-wide conventions live in this
file; domain specifics live in the nearest subdirectory CLAUDE.md.

## Working Conventions

### Before you start

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

- **Opening any GitHub issue** (via `mcp__github__issue_write`, whether for a
  spec/plan or a quick-fix bug/feature report): `issue_write` does NOT apply a
  repo issue template — that's a GitHub web-UI-only convenience (the "New issue"
  picker), invisible to the API. Read the matching template under
  `.github/ISSUE_TEMPLATE/` yourself (`bug_report.md` or `feature_request.md`)
  and structure the body to match it — plain-language sections first, a "For
  Claude" fold-out last — rather than writing free-form.

- **Before creating a branch**: ask the user — worktree or branch switch? Do not
  choose for them. When an issue isn't already required (i.e. quick fixes, not
  specs/plans), also ask whether to anchor the branch with one, and honor a
  decline — create the branch without an issue via the paths below.

- **Before writing any file (spec, code, config)**: be on the feature branch.

### Branches and worktrees

- **Worktree**: with an issue, `gh issue develop <number> --name <branch>` (no
  `--checkout`), then `git worktree add .worktrees/<branch> <branch>`. If the
  user explicitly declined an issue, skip `gh issue develop` and create the
  branch directly: `git worktree add -b <branch> <abs-path> origin/main` (name
  the base — local `main` is often behind).

- **Stacked branch** (build on an unmerged branch):
  `gh issue develop <num> --name <branch> --base <parent-branch>` links a branch
  off a non-`main` base; then `git worktree add`. Gives a clean diff + enforced
  merge-after-parent — but base ≠ main skips `claude-review` (dbt Cloud CI still
  runs; it is not base-gated — see `.github/CLAUDE.md`).

- **A stacked `git worktree add -b <new> <abs-path> <parent-branch>` sets the
  new branch's upstream to the PARENT** — a bare `git push` then pushes your
  commits onto that branch, which is usually someone else's. Run
  `git -C <worktree> branch --unset-upstream` immediately after creating it,
  then `git -C <worktree> push -u origin <new-branch>`.

- **Linking an existing remote branch to an issue**:
  `mcp__github__create_branch` and GraphQL `createLinkedBranch` both no-op when
  the branch already exists. Delete the remote branch, then
  `gh issue develop <num> --name <branch>`, then re-push local commits.
  `git push origin --delete <branch>` is classifier-blocked as a destructive git
  action even with consent — if the delete is refused, create the branch under a
  NEW name and `gh issue develop --name <new-name>` instead of deleting.

- **Worktree commands**: Path-flag-driven tools must name the worktree
  explicitly. Use `git -C <worktree>` on every git call (bare `git` from the
  main repo silently commits to `main`) and
  `uv run dbt ... --project-dir <worktree>/src/dbt/<project>` on every dbt call
  (do NOT use `uv --directory <worktree> run dbt ...` — that overrides cwd to
  the worktree root where `dbt_project.yml` doesn't exist). For Python execution
  from the main repo, prefix `VIRTUAL_ENV=` and use
  `uv --directory <worktree> run python ...` — bare `uv run --active` reads the
  main repo's `.venv` and misses worktree-only changes. `uv --directory` also
  resolves a relative _script_ path under the worktree, so a main-repo script
  path breaks — pass an absolute script path or run it from the main repo.
  Otherwise prefer absolute paths.

- **Bash cwd persistence is version-dependent — treat it as unknown.** Older
  builds reset every call to the main repo root; current builds carry a `cd`
  forward (the harness notes "Session cwd remains ..."). Rely on neither: prefix
  commands with `pwd &&`, and for worktree work include `cd <worktree> &&` in
  the SAME command (or use absolute paths) — tools that resolve relative paths
  from cwd (`trunk check`, `pytest`, `sed -i`) silently operate on the wrong
  checkout's copies and report a false "clean".

- **Worktree file operations must name the worktree path** —
  `/workspaces/teamster/.worktrees/<branch>/<path>`, never
  `/workspaces/teamster/<path>`. Editing the main path silently leaves the
  worktree unchanged and dirties `main`, and the worktree commit then reports
  "nothing to commit". IDE Pyright diagnostics on worktree files are
  false-positive-prone for the same reason: it resolves imports against the MAIN
  checkout, so worktree-only signature or symbol changes surface phantom
  `unknown import` / `no parameter named X` errors. Trust `uv run` executed
  inside the worktree, not the IDE.

- **Worktree Read/Edit and Bash `cd <worktree>` re-inject that worktree's
  CLAUDE.md files (~40KB each) on every call**; `git -C <worktree>` and
  `uv run dbt --project-dir <abs-worktree>` from the MAIN cwd, and `Write`
  (content-exempt), do NOT. For a large multi-file worktree refactor, delegate
  the edits to subagents — their context absorbs the injection — and verify via
  `git -C <worktree> diff` from the main repo. With no subagents available,
  `Write` a Python script to `.claude/scratch/` and run it by ABSOLUTE path from
  the main repo cwd (neither step re-injects); assert each anchor matches
  exactly once, abort otherwise, and verify the same way.

- **`git worktree add` with a RELATIVE path resolves against the shell cwd**,
  which drifts after a foreground `cd` into another worktree — pass an ABSOLUTE
  path (`git worktree add /workspaces/teamster/.worktrees/<branch> <branch>`) or
  it nests one worktree inside another.

- **Branch switch**: with an issue,
  `gh issue develop <number> --name <branch> --checkout`; if the user explicitly
  declined an issue, `git checkout -b <branch>`.

### Git hygiene

- **Git naming**: Commit messages and branch names use
  [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/). Branch
  naming: `<gh-username>/<commit-type>/claude-<brief-description>` (get username
  from `mcp__github__get_me`).

- **Git staging**: Prefer `git add -u` — naming protected paths triggers the
  hook, `git add -A` can stage unrelated files. Subagents must name specific
  files in `git add` — never `-u`, `-A`, or `.`.

- **Refactor regex sweeps include `*.md`**: a model/column rename's
  `grep -rl --include='*.sql' --include='*.yml'` misses CLAUDE.md
  hash-derivation examples, plan/spec docs, and inline doc cross-refs. Use
  `--include='*.{sql,yml,md}'` (or drop `--include` entirely) for any rename
  that changes a model or column name.

### Subagents and workflows

- **Dispatching subagents**: Subagents do not auto-invoke skills. In the
  dispatch prompt, name the exact `Skill` tool calls the subagent must run
  before starting work (e.g. `Skill` with
  skill=`dbt:using-dbt-for-analytics-engineering` for a dbt review). For
  negation goals (remove X, no Y), list anti-patterns explicitly — subagents
  otherwise re-introduce familiar idioms (`dbt_utils.deduplicate`,
  `select distinct`, `qualify row_number()=1`).

- **Subagents cannot Write report/findings files** — the harness refuses with
  "Subagents should return findings as text". Have them return the report as
  their final text; the coordinator persists it to scratchpad.

- **Edit-task dispatches must say "do the edits YOURSELF — do NOT dispatch
  sub-agents."** Without it an agent may re-delegate, stall waiting on its
  children, and self-report progress that `git status` disproves.

- **Subagent model/effort**: when a skill carries its own model-selection
  guidance (e.g. subagent-driven-development), follow the skill; this line only
  binds its tiers to models. Mechanical scoped tasks (1-2 files, precise brief)
  -> `haiku` (no effort parameter -- omit it); integration/debugging
  implementers -> `sonnet` at `high`; review and re-review dispatches ->
  `sonnet` at `xhigh`; design work -> `opus` at `high`; final whole-branch
  review -> `opus` at `xhigh`. When none of these clearly apply, omit both
  overrides. The `Agent` tool accepts only `model` — effort is settable on
  Workflow `agent()`, not `Agent`, so via `Agent` pass the model and drop the
  effort tier.

- **Subagent multi-step bail risk**: subagents can abandon multi-step tasks
  partway through. Scope dispatches to one file / one commit; inspect the file
  diff and `git log` before marking complete — don't trust the self-report.

- **Tell subagents to run builds in the FOREGROUND.** A subagent that
  backgrounds a long `dbt build` strands itself waiting on the notification and
  returns having written nothing. Also never run two dbt subagents concurrently
  against one worktree — they share `target/` and corrupt the partial-parse
  manifest.

- **A subagent's "pre-existing failure" baseline is the working tree AS
  DISPATCHED**, including your own uncommitted edits. "Already failing before I
  touched anything" can mean "failing because of the coordinator's change."
  Check whether your own work caused it before accepting that framing.

- **Subagent worktree dispatches must spell out the absolute worktree path**: a
  subagent starts in the MAIN checkout, so the dispatch prompt must give the
  worktree path and mandate `git -C <worktree>` + `uv run` from it (bare edits
  hit `main` silently), and state that IDE Pyright errors on worktree files
  (`reportMissingImports`, "not accessed", "not iterable") are expected false
  positives — trust `uv run` inside the worktree, not the IDE.

- **The `Workflow`-tool orchestrator is unreliable for long fan-outs in this
  Codespace** — runs stall mid-run, and a window reload can leave a prior run
  orphaned-but-alive, still spawning branches and worktrees. Prefer discrete
  main-loop `Agent` dispatches for multi-batch work (one unit lost on failure,
  resumable); if you must run a Workflow, check for and kill a leftover prior
  run after any reload BEFORE relaunching.

- **Workflow run hygiene**: a dead run = its journal
  (`~/.claude/projects/<proj>/subagents/workflows/wf_<id>/journal.jsonl`) stops
  growing for ~2min with no live `dbt`/agent procs. Its `isolation:'worktree'`
  dirs are `.claude/worktrees/wf_<id>-N` (NOT the repo `.worktrees/`; left
  `locked` when orphaned — `git worktree unlock` then `remove --force`).
  `TaskStop` only sees tasks launched in the CURRENT session — a Workflow from a
  prior (reloaded) session isn't in the registry; clean it at the
  process/worktree level. Concurrency cap = `min(16, cpu_cores-2)` (4-core
  Codespace → 2; raising it needs a larger machine, whose restart kills
  in-flight runs).

### Merging and resuming

- Before resuming an existing branch, merging `origin/main`, resolving a
  conflict, or diagnosing a CI failure in a file your branch never touched,
  invoke the `resuming-a-branch` skill (merge-tree verification, lockfile
  conflicts, Codespace-restart ref desync, docs-only reverts).

### Consent, safety, and verification

- **Auto-classifier doesn't see verbal approval or `AskUserQuestion` answers** —
  only the assistant message immediately preceding the tool call. After
  out-of-band consent, re-confirm in plain text the same turn or the write will
  be denied. Common surfaces: `git worktree add -b` / `git checkout -b`,
  `git push origin main` (route through a PR or have the user push), bulk Asana
  `create_tasks`. If the user hasn't ruled an issue out, open a minimal one
  (title + 1-2 sentences) and use `gh issue develop`; if the user explicitly
  declined an issue, create the branch directly (`git worktree add -b` /
  `git checkout -b`) and re-confirm that consent in plain text the same turn so
  the classifier (which can't see `AskUserQuestion` answers) allows it.
  `gh issue develop --name <branch>` also fails when the branch contains trigger
  words like `log`, `auth`, `secret` — rename and retry.

- **Destructive SQL / shared-resource mutations need _named_ consent.** The
  auto-classifier ("Cloud Storage Mass Delete", "Shared Cluster Mutation")
  rejects a warehouse `DELETE`/`DROP` or a bulk `launch_multiple_runs` even
  after "yes"/"resume" and an agent plain-text re-confirm — the USER's message
  must name the specific operation + target ("delete rows where X from
  `dataset.table`"). Draft the exact statement and have them restate it, or hand
  it to their terminal. For `launch_multiple_runs` the block fires even at
  `confirm=False` (preview), and the dagster MCP has no `create_backfill` — hand
  a partition-range backfill to the user to launch from the Dagster UI
  (splitting into per-partition `launch_run`s to dodge the bulk classifier
  bypasses intent — don't).

- **Pushing to `main` is forbidden** (user policy, and the classifier
  hard-blocks it regardless of in-conversation consent) — hand any main push to
  the user; do not retry. Editing and committing on LOCAL `main` is allowed when
  the user asks; anything remote goes through a branch + PR.

- **Smoke-test the runtime path, not just imports**: `hasattr(cls, "method")`
  and `python -c "import X"` pass even when a third-party SDK sub-resource (e.g.
  `googleapiclient` `.files()`, OpenAI sub-client) lacks the attribute at call
  time. Before claiming a fix is verified, call the method — minimally against a
  mock or `try` block — not just `hasattr`.

### Pull requests and CI

- **Pull requests**: Squash merge. Use `.github/pull_request_template.md` as the
  PR body.

- **PR project linkage**: PRs auto-appear on project boards via issue refs
  (`Refs #N`, `Closes #N`) in the body. Do NOT `gh project item-add` a PR.

- **Always invoke `superpowers:receiving-code-review` BEFORE processing
  `claude-review` findings**, and post a per-finding verdict as a PR comment — a
  silent fix reads as an unaddressed review. For everything else about PR review
  and CI (claude-review mechanics, dbt Cloud CI state and warnings,
  commit-status vs check-run surfaces, deploy check-runs, `not_planned`
  handoffs), invoke the `pr-ci-review` skill.

### Tooling discipline

- **Python**: Always `uv run` — never bare `python`, `python3`, or
  venv-installed tools (`dbt`, `dagster`, etc.).

- **Transient Python deps**: Use `uv run --with <pkg> python script.py` for
  one-off scripts needing a package not in `pyproject.toml` — don't
  `uv add --dev` for throwaway tooling.

- **Credentialed one-offs run under pytest, never `uv run python`.** The autouse
  session fixture in `tests/conftest.py` bootstraps 1Password secrets into the
  process, so live SFTP / API pulls, asset `materialize()`, and
  `dagster definitions validate` all work — wrap the one-off as a throwaway
  `tests/**/test_zz_*.py`, run `uv run pytest <path> -s`, and delete it after. A
  plain `uv run python script.py` gets NO secrets and fails on unset variables;
  do not conclude a credential is unavailable from that failure, and do not
  reach for `op` (hook-blocked). Details in [tests/CLAUDE.md](tests/CLAUDE.md).

- **IDE selection arrives only via `<ide_selection>` tags**, not
  `<ide_opened_file>` (which only names the open path). When the user references
  "this" without an `<ide_selection>`, ask for the snippet — don't guess.

- **Arm the Monitor in the same turn you say you'll watch something.** A monitor
  that has exited is indistinguishable from one still waiting — both are silent.
  Stating an intention is not a mechanism.

- **Never assert remaining context as fact** — there is no token counter, the
  harness compacts automatically, and a felt sense of a long session is not
  evidence. Truncating analysis or handing off work on that basis costs more
  than finishing it.

- **Before claiming a harness artifact (rewritten output, phantom rendering,
  truncated literal), verify with a DERIVED value** — line length, `grep -c`, a
  checksum. A misread is far likelier than a rewriting pipeline, and a plausible
  substitute string survives eyeballing where a length does not.

- **Built-in tools over Bash**: Use dedicated tools for file I/O (Read, Grep,
  Glob, Edit, Write). Bash is only for commands with no dedicated tool (`git`,
  `uv run`, `gh`, `docker`, `trunk`, `ls`). On the VSCode-extension (native)
  build of Claude Code ≥2.1.117, Grep/Glob are folded into Bash and absent as
  standalone tools (`Grep` → "No such tool available") — search with `rg`/`grep`
  via Bash instead.

- **Don't pipe `Bash(run_in_background=true)` output through
  `head`/`tail`/`grep`**. The pipe truncates what reaches the output file —
  defeats the purpose. Pipe the raw stream; filter with Read/Bash after.

- **Verify tool-call results for resource creation/update**: syntax errors in
  structured tool-call parameters (malformed closing tags, misnested blocks) can
  silently produce corrupted values — the call succeeds without error, just with
  the wrong payload. After any call that creates or updates a resource with
  string fields (issue title, PR body, commit message, etc.), check the returned
  values match intent before moving on.

### Linting and markdown

- **Do not run `trunk fmt` or `trunk check` as a routine** — the pre-commit hook
  formats and the pre-push hook checks. But a clean commit hook is NOT
  lint-clean: before pushing SQL/YAML/markdown, run
  `/workspaces/teamster/.trunk/tools/trunk check --force <files>` with cwd
  inside the checkout you edited.

- **Suppress** with `trunk-ignore(linter/rule): reason` on the line immediately
  before the flagged line — never linter-native disable syntax.

- Binary locations, worktree invocation, markdownlint rules that fire only at
  CI, and concurrent-run artifacts: invoke the `trunk-lint` skill.

### Environment and external tools

- **Claude CLI**: Not on `$PATH` — user must run `claude` commands in their
  terminal, not via Bash tool.

- **Verify third-party tool behavior from source**: Before describing how an MCP
  server, dbt CLI flag, or `gh` subcommand behaves, open the source or run
  `--help` — do not extrapolate from general knowledge.

- **Docs**: "docs" means the `docs/` folder (MkDocs site), not CLAUDE.md files.
  "The docs", "the ref doc", or "the reference" means the **published** page in
  the `mkdocs.yml` nav (e.g. `docs/models/<dashboard>-data-model.md`) — NOT the
  design specs and implementation plans under `docs/superpowers/`, which are
  working documents excluded from the nav. When asked whether docs are stale,
  audit the published page against the shipped code first; a spec/plan
  describing a superseded design is expected, a wrong published page is a bug.

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

PII-tagging precedent in staging (powerschool) is **narrower** than this list —
it omits gender, race/ethnicity, and internal/student ids. For a PII-heavy new
model, confirm scope (direct-only vs direct+indirect) with the user before
tagging.

## Superpowers skill overrides

- **Branch creation always goes through the issue-and-branch flow in _Working
  Conventions_** — no exceptions for `superpowers:brainstorming`'s "Write design
  doc" step, `superpowers:writing-plans`' "Save plans to:" step, or
  `superpowers:using-git-worktrees`' worktree-consent prompt. Pause those
  skills, run the flow, then write specs to `docs/superpowers/specs/...` or
  plans to `docs/superpowers/plans/...` on the new branch. Default to
  `gh issue develop` so the branch is linked to an issue; only create a branch
  standalone (`git worktree add -b` / `git checkout -b`) when the user
  explicitly declines an issue — re-confirm that consent in plain text the same
  turn.

- **`trunk check` the spec/plan `.md` you write before pushing** — markdownlint
  (MD040 fenced-block language, MD036, MD029 ordered lists) fires only at
  pre-push/CI, not the pre-commit `fmt` hook; checking only the code files
  misses a doc-only Trunk failure. Use `--force --no-fix </dev/null`: `--force`
  is REQUIRED (without it a committed file is git-diff-check-skipped and
  markdownlint under-reports — a false "No issues"), and `--no-fix </dev/null`
  avoids the interactive "Apply formatting?" hang.

- **`finishing-a-development-branch` / `using-git-worktrees` tests & setup**:
  this repo uses `uv`, not `poetry`/`pip`, and
  `uv run dbt build --select <model>+` should run alongside the skills' other
  tests.

- **Before brainstorming a fix for a GitHub issue**: verify the issue's claims
  (row counts, bucket sizes, reproduce queries, named files/columns) against
  current code and data. Issue bodies drift — code moves, data changes, prior
  PRs land. Re-run the diagnostic before designing.

- **Ponytail yields to superpowers process skills**: when both trigger, run the
  superpowers skill (`brainstorming`, `test-driven-development`, etc.) —
  ponytail governs the size of what gets built inside it, not whether it runs.

- **At the investigation→build pivot, ask about `superpowers:brainstorming`** —
  a design settled in conversation doesn't waive it on its own. Ask the user
  whether to run it; skip only when they say so.

## Compact Instructions

When summarizing the conversation, always preserve:

- The original task/request verbatim, plus constraints and scope decisions the
  user stated ("don't touch X", "we decided against Y" — and why).
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

- **Before adding to any CLAUDE.md file**: beyond the skill's
  brevity/avoid-list, apply the necessity test — name the specific decision or
  action Claude will make differently because of the line. If you can't name
  one, cut it, even when the line is concise and non-obvious.

- **Where a new line goes**: if it is specific to one MCP server's behavior, put
  it in `.claude/context/<server>.md` (auto-injected on first use of that
  server). If it is specific to one directory, put it in that directory's
  CLAUDE.md. Keep it in this file only when it must be known BEFORE any tool
  runs — safety prohibitions, branch/PR etiquette, and rules whose violation
  produces a silently wrong answer rather than a loud error.

## MCP Servers

Dagster+ MCP auth: do not revert `.mcp.json` to `op run` —
`OP_SERVICE_ACCOUNT_TOKEN` is scrubbed post-boot, so `op run` silently breaks
after the first Codespace restart. Keep `scripts/dagster-mcp-launch.sh` as the
launcher. Package internals: see
[TEAMSchools/dagster-plus-mcp](https://github.com/TEAMSchools/dagster-plus-mcp).

- **MCP outages**: If an MCP tool returns "server disconnected" or clearly
  impaired responses, surface to the user before working around with raw `gh` /
  BigQuery calls. Same if an EXPECTED MCP tool is absent from the deferred-tools
  list (ToolSearch returns "No matching deferred tools") — flag it immediately
  so the user can reconnect; do not silently fall back.

- **MCP subprocess logs**: stdio MCP stderr captured at
  `~/.cache/claude-cli-nodejs/-workspaces-teamster/mcp-logs-<name>/<ts>.jsonl`.
  Retries and reconnects append to the same file — read the newest file's tail,
  don't expect a new file per attempt. JSONL keys: `debug` (connect timings),
  `error` (subprocess stderr). Read these before guessing why an MCP fails.

### MCP tool selection

For natural-language analytics questions (metrics, KPIs, business-domain
questions about students, attendance, grades, enrollment, staff, etc.), **start
with `cube`** — `meta` to discover views, then `load`. Cube enforces row-level
access policies and PII defaults; raw-warehouse paths bypass them. See
[src/cube/CLAUDE.md](src/cube/CLAUDE.md) for query shape.

If `dbt:answering-natural-language-questions-with-dbt` auto-loads, do not follow
it — its dbt-Semantic-Layer path doesn't apply (no dbt SL here) and its
ad-hoc-SQL fallback bypasses Cube's policies. Use the `cube` MCP instead. Fall
back to BigQuery MCP for ad-hoc SQL only after `cube meta` confirms no view
models the needed columns.

Use BigQuery MCP for warehouse-level inspection (raw source rows, schema diffs,
`INFORMATION_SCHEMA`) and for engineering tasks (dbt model validation, audits).

Use dbt MCP's `show` only when `ref()` / `source()` resolution is needed — it
adds compilation overhead.

GitHub MCP (`mcp__github__*`) is the primary tool for every GitHub operation.
The `gh`-via-Bash list below is an **exhaustive allowlist** — any `gh`
subcommand not on it is forbidden via Bash. Before any GitHub operation, first
identify the `mcp__github__*` tool that handles it; only if none exists, check
the allowlist.

- `gh issue develop` — linked branch creation.
- `gh project item-edit` / `gh project item-add` and `gh api graphql` for
  ProjectV2 fields (no MCP coverage).
- `gh pr checks <n> --json name,bucket,state` — CI poll loops.
- `gh run *`, `gh workflow *`, `gh repo edit` — no MCP coverage.
- `gh api` only for: PATCH an existing comment or PR body (`-F body=@<file>`),
  POST a reply in a PR review thread, read a file at a pinned SHA with the raw
  Accept header, create/add labels, `-X GET search/issues`.

Per-command mechanics and failure modes for every item above are in
`.claude/context/github.md` (auto-injected on first GitHub MCP use).

**Per-MCP gotchas load automatically.** The `tool-gotchas` PreToolUse hook
injects `.claude/context/<server>.md` the first time each MCP server is used in
a session (and again after a compaction), so this file no longer carries them.
The file name must match the server segment of the tool name
(`mcp__<server>__<tool>`). To add or change guidance for a server, edit that
file — no hook or settings change is needed.

**Warehouse writes stay with the user**: the BigQuery MCP is SELECT-only, and
the `bq` CLI runs on user credentials that expire mid-session, so warehouse
DML/DDL must be handed to the user's terminal — never worked around.
