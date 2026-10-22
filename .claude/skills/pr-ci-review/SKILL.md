---
name: pr-ci-review
description:
  "Use when opening, monitoring, or responding to review on a pull request in
  this repo: reading claude-review bot findings, checking dbt Cloud CI state
  before pushing fixes, fetching CI warnings, telling commit statuses from check
  runs, dagster-cloud-deploy check-runs, re-triggering claude-review via draft
  toggle, the not_planned/Asana handoff convention, what dbt Cloud CI does and
  does not build (state:modified selection, kipptaf-only), and which GitHub
  Actions fire on a PR (claude-review gating, branch deployments, push-paths
  drift)."
---

# pr-ci-review

- **`not_planned` closure with a "Tracked in Asana: <url>" comment = handoff to
  Ops, not rejection.** The `TODO(#NNNN)` pointer is still live. Reopen the GH
  issue and apply the `ops-tracked` label; it stays open until the linked Asana
  task completes.

- **Check dbt Cloud CI state before pushing fixes**: pushing cancels an
  in-progress dbt run and restarts it. Before pushing a CI-fix commit, confirm
  dbt Cloud is in terminal state; if it's still running, wait or ask the user.
  Bundle multiple CI-fix commits into one push.

- **After dbt Cloud CI passes on a PR**: fetch its warnings before declaring
  done (`warning_only` call in `.claude/context/dbt.md`). Local relationships
  warnings absent from CI are stale-dev `--defer` drift; ignore. CI warnings
  unchanged from main are pre-existing — `gh search issues` for a tracker before
  filing.

- **The `claude-review` bot asserts repo conventions that may not be enforced.**
  Verify each convention claim against existing models before applying — its
  findings are advisory, and `git grep` settles it faster than complying.
  **Always invoke `superpowers:receiving-code-review` BEFORE processing
  `claude-review` findings** — verify each claim (including its file:line
  citations) against the code before relaying or replying, not after. Fixing a
  finding in code is not a reply — post a per-finding verdict as a PR comment
  (declines included, with reasons). A silent fix reads to a human reviewer as
  an unaddressed review.

- **A dispatched code-review subagent's "confirmed non-issue" dismissals aren't
  authoritative** — verify its convention claims (dismissals as much as flags)
  against the guide text + `git grep` before relaying.

- **A PR's CI lives on two disjoint surfaces**: dbt Cloud is a commit _status_
  (`pull_request_read get_status` / `gh api commits/<sha>/status`); Trunk /
  CodeQL / `claude` are _check runs_ (`get_check_runs` /
  `commits/<sha>/check-runs`). Check both before calling a PR green. Trunk's
  check-runs are RE-CREATED on each push, so a `gh pr checks` poll gating on
  "nothing pending" can sample the gap between them and report done prematurely
  — re-check after a delay. A PR with all checks green but
  `mergeable_state: blocked` (from `gh api repos/<owner>/<repo>/pulls/<n>`) is
  awaiting a required review approval (CODEOWNERS `src/dbt/` =
  analytics-engineers), not a CI failure.

- **`claude-review` skips PRs whose every file matches its exclusions** (docs,
  lockfiles, CSVs, editor and docs-site config; list in the `paths:` filter of
  `claude-code-review.yaml`). Such a PR gets no review comment: do not wait for
  one, and drop the "Review the Claude Code Review comment" checkbox from its
  body.
- **Re-read the PR state before any follow-up push or body edit.** A small docs
  PR can merge within minutes of opening. Merge auto-deletes the branch, and a
  later `git push` silently recreates it as an orphan (`* [new branch]` in the
  output is the tell), while a body PATCH lands on a closed PR. If
  `merged: true`, start a new branch from `origin/main` and cherry-pick.
- **`claude-review` fires only on PR `opened` / `ready_for_review`**, never on
  `synchronize` — it does NOT re-run when you push fixes, so don't wait or
  monitor for a re-review after a fix push. To get it onto code pushed after its
  pass, toggle draft state: `mcp__github__update_pull_request` with
  `draft: true`, then again with `draft: false`, or GraphQL
  `convertPullRequestToDraft` then `markPullRequestReadyForReview`. REST
  `gh api -X PATCH .../pulls/<n> -f draft=true` silently no-ops (returns
  `draft: false`, no error).

- **Read `claude-review` findings by enumerating ALL issue comments**, newest
  and longest first. It posts as **`github-actions[bot]`**, not a `claude`-named
  user, so filtering by a "claude" login returns nothing. It may leave TWO
  comments (a "Reviewing…" stub plus a findings comment) or instead EDIT the
  stub in place, before or after the check-run reports `success`, and a re-fired
  run creates a NEW comment even with `use_sticky_comment: true`. So gate a
  findings-poll on the body STARTING with the completion header
  `**Claude finished @` — never on the absence of "in progress" (a finding can
  quote that phrase and hang the poll), a cached comment id, a length threshold,
  or the check-run conclusion.

- **A merged PR's CI status is not evidence the change was validated** — a PR
  merged mid-CI leaves a permanent `dbt Cloud: failure` that is a cancellation,
  not a build failure (mechanics in `.claude/context/dbt.md`).

- **`dagster-cloud-deploy / deploy` emits one same-named check-run per code
  location** (~5) — `get_check_runs` returns duplicates; wait for ALL to reach a
  terminal conclusion before calling the deploy green. A shared-library change
  (e.g. `libraries/dlt/`) redeploys every consuming location, not just the ones
  whose config you edited.

## dbt Cloud CI builds only kipptaf

The dbt Cloud CI job (`Build - CI (Modified)`, dbt Cloud project 211862) runs
`dbt build --select state:modified+ --full-refresh` with target `staging`,
deferring to the Staging environment, against the `kipptaf` project alone. A PR
confined to a district project (`kipp{newark,camden,miami,paterson}`) or a
source-system package selects zero models under `state:modified+` unless it
changes a kipptaf-consumed `source()` schema (column set) — so the dbt Cloud
check goes green **trivially, not as validation** (a no-op run). A dbt-only PR
also gets NO branch deployment (the `pull_request` paths in
`.github/workflows/deploy-prod-*.yaml` exclude `src/dbt/**`), so **nothing in CI
builds those models** — a local `dbt build` is the only pre-merge validation,
and they are first exercised in prod after merge. Never call such a PR
CI-validated.

## dbt Cloud CI state comparison

`state:modified+` hashes every source node through `{{ target.name }}`
rendering. The CI job and the parse job in its `deferring_environment_id` must
share `target_name`, or every source with the target-conditional schema pattern
hash-mismatches and fans out to rebuild the whole graph.

`state:modified+` is branch-vs-deferred-environment, NOT commit-vs-commit. A
docs-only or `.md`-only push to a branch that already modifies dbt models
re-runs the whole selection. Batch doc commits before pushing, or land them in a
separate PR. Verify what a run actually built with `creation_time` in
`region-us.INFORMATION_SCHEMA.TABLES` filtered to `dbt_cloud_pr_<job>_<pr>%` —
step duration and warning counts are both weak proxies.

A refactor touching many models pulls them into `state:modified+`, so CI builds
models it has never built — expect latent `severity: error` failures unrelated
to your change (duplicate PKs already sitting in prod). Query prod for the same
count before assuming you caused it, and budget for triage when scoping a wide
sweep.

### Re-triggering Build - CI

Prefer `mcp__dbt__retry_job_run(run_id=<failed run>)`: it retries the existing
run and keeps the PR-schema override, which `trigger_job_run` loses. But a retry
invokes `dbt retry`, which replays the prior run's compiled SQL — the same
applies to CI's own auto-retries. After fixing external state (defer relations,
transient BQ errors), get a fresh `dbt build` with an empty commit + push
instead.

### Stale staging defer copies

`Clone - Staging (Modified)` clones only `state:modified` models, not their
parents. When CI fails on a stale staging defer table for an unmodified upstream
(column missing after a recent merge), trigger the full clone through
`mcp__dbt__trigger_job_run` with the `Clone - Staging (On-Demand)` job ID from
`mcp__dbt__list_jobs`, or
`uv run dbt clone --select <upstream> --target staging` (a shared write: _Shared
staging writes_ in `.claude/rules/dbt-yaml.md`). After the clone succeeds,
empty-commit + push re-triggers Build - CI.

`Clone - Staging` refreshes only kipptaf-level relations — NOT district-level
`zz_stg_kipp<district>_*`. A CI orphan / row-count delta that reconciles exactly
against per-district prod-vs-`zz_stg` gaps is that staleness, not your change;
re-running Clone - Staging won't fix it. Seeding the district copies is the
single-PR workflow in `src/dbt/kipptaf/CLAUDE.md`.

A `Clone - Staging` run recreates the `zz_stg_*` tables while it runs, so a CI
run in flight at the same time fails `Not found: Table zz_stg_kipptaf_<x>.<y>`
on models the PR never touched. Check `list_jobs_runs` for an overlapping clone
before reading the failure as a bug, wait for the clone to finish, then re-push
for a fresh build.

**Stale per-PR shadow** (distinct from a stale staging defer): a model that was
`state:modified` in an earlier run (e.g. before the branch merged `main`) but is
now unmodified leaves a stale copy in the per-PR schema
(`dbt_cloud_pr_<job>_<pr>_<schema>`, one dataset per dbt custom schema). dbt
prefers an existing same-schema relation over the staging defer, so consumers
fail `Name <col> not found` even when `zz_stg_*` has the column. Confirm via
`INFORMATION_SCHEMA.COLUMNS` on the per-PR vs `zz_stg_*` schema, then have the
user drop the stale per-PR relation (match `drop view`/`drop table` to its type)
— or `drop schema ... cascade` the whole `dbt_cloud_pr_<job>_<pr>_*` set to
avoid model-by-model whack-a-mole — and re-run. Claude is DDL-blocked (BQ MCP /
`bq` are SELECT-only).

## Editing a `sources-kipp*.yml` schema fans out `state:modified+`

Changing a source's schema (e.g. adding a `target=staging` branch) marks the
WHOLE source `state:modified` — CI's `state:modified+` builds EVERY kipptaf
model reading it, not just your target. A district model dropped from code but
lingering as a stale prod table is absent from the prod manifest → clone-skipped
→ its kipptaf consumer fails CI `Table not found`. Fix such frozen/retired
tables by declaring them a BQ-native source (`sources-bigquery.yml`, plain
hardcoded schema, no target branch) so kipptaf reads prod regardless of target.

## GitHub Actions on a PR

- `claude-code-review.yaml` — auto-reviews PRs matching the path filter above. A
  PR editing a workflow runs that PR's own copy of it, so workflow changes
  review themselves. **Gated to `base=main` (`branches: [main]`)** — a **stacked
  PR** (base = another feature branch) gets no auto-review. dbt Cloud CI is ALSO
  base-gated, by dbt Cloud itself: it triggers only for PRs whose base is the
  environment's branch (`main`), so a stacked PR gets NO `dbt Cloud` commit
  status at all. Do not wait or monitor for it; local `--target dev` builds plus
  `zz_stg_*` seeding are the pre-merge validation, and CI first fires on the
  re-target to `main`. Only Trunk runs on a stacked PR. Review a stacked PR via
  `superpowers:requesting-code-review` or an `@claude` PR comment (`claude.yaml`
  is comment-triggered, not base-gated). A base-retarget after the parent merges
  does NOT re-fire `opened`, so `claude-code-review` does not auto-trigger then.

- **`claude-code-action` headless deadlock**: the action breaks its SDK loop on
  the FIRST result (`base-action/src/run-claude-sdk.ts`), so a run that
  dispatches background subagents ends with them orphaned and reports `success`
  having posted nothing (upstream #1462 / #1499). `Agent`, `Workflow`,
  `ScheduleWakeup`, `SendMessage` and `Monitor` are NOT gated by
  `--allowedTools` — deny them via `--disallowedTools` in `claude_args`. A
  second `--allowedTools` / `--disallowedTools` ACCUMULATES with the action's
  own list rather than replacing it (`parse-sdk-options.ts`
  `ACCUMULATING_FLAGS`), so adding tools cannot strip `update_claude_comment`.

- **Debugging a silent `claude-review`**: `display_report: true` appends the
  transcript — final assistant message, denied tool calls — to the run's **job
  summary**, the only place they appear. Not in the REST API, and not in the
  step log (`show_full_output`-gated). Read it before theorising.

- **Which ref a workflow runs from**: `pull_request` runs the PR's OWN copy, so
  a workflow change tests itself on that PR. `issue_comment` (`claude.yaml`)
  runs the DEFAULT-branch copy — an `@claude` mention cannot exercise an
  unmerged `claude.yaml`; probe such a change through a `pull_request` workflow
  instead.

- **Branch deployments build only on a NON-draft PR** —
  `deploy-prod-<location>.yaml` gates the deploy job
  `if: ${{ !github.event.pull_request.draft }}`. To get a branch deployment
  (e.g. to test a change before merge), open the PR ready-for-review, not draft.
  A change to a shared `pull_request`-path file (`uv.lock`, `Dockerfile`,
  `src/teamster/core/**`) fans a branch-deploy build out to ALL five locations,
  not just the one you touched — including when that shared change arrives via a
  `main`-merge commit on the branch: the `pull_request`/`synchronize` `paths`
  filter matches the pushed delta (which includes the merge commit), NOT the net
  three-dot PR diff (where the merged-in files, now equal to main, don't
  appear).

- **A markdown-only commit still re-triggered the `kipptaf` deploy** on
  `pull_request`, despite `"!**/CLAUDE.md"` in BOTH trigger blocks of
  `deploy-prod-kipptaf.yaml`. This contradicts the pushed-delta model above,
  which predicts no run — one of the two is incomplete, and no mechanism is
  established here. Plan for the cost: a docs-only push to a PR is NOT free, so
  batch doc changes into the code commit rather than splitting them off to
  "avoid CI".

- **Each `deploy-prod-<location>.yaml` push-`paths` must list every dbt package
  in that district's `src/dbt/<district>/packages.yml`** (`src/dbt/pearson/**`,
  etc.). Drift silently skips that district's prod deploy on a shared
  source-package change, stranding it on stale code. After merging a
  source-package change, confirm every consuming district deployed
  (`gh run list --branch main`); a post-merge prod failure whose run tags show
  the OLD `dagster/git_commit_hash`/image is a missed/lagging deploy, not a code
  bug. The `pull_request` `paths` intentionally exclude `src/dbt/**` (dbt Cloud
  CI covers those); only the `push` section needs them.

- **The same push-`paths` drift hits shared Dagster library code**, not just dbt
  packages: `deploy-prod-<location>.yaml` must list every
  `src/teamster/libraries/<lib>/**` the location imports, or a shared-library
  change silently skips that location's deploy. After merging a library change,
  confirm the consuming location actually **reloaded** before acting on the new
  code: `mcp__dagster__get_location_load_history` → newest entry
  `loadStatus: LOADED` with a matching `commit_hash`. A green Actions deploy job
  ≠ agent reloaded, and a missing push-path means it never deployed at all.
