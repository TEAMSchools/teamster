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

- **After dbt Cloud CI passes on a PR**: fetch warnings with
  `mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)` before
  declaring done. Local relationships warnings absent from CI are stale-dev
  `--defer` drift; ignore. CI warnings unchanged from main are pre-existing —
  `gh search issues` for a tracker before filing.

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

- **`claude-review` fires only on PR `opened` / `ready_for_review`**, never on
  `synchronize` — it does NOT re-run when you push fixes, so don't wait or
  monitor for a re-review after a fix push. To get it onto code pushed after its
  pass, toggle draft state via GraphQL `convertPullRequestToDraft` then
  `markPullRequestReadyForReview`; REST
  `gh api -X PATCH .../pulls/<n> -f draft=true` silently no-ops (returns
  `draft: false`, no error).

- **Read `claude-review` findings by enumerating ALL issue comments**, newest
  and longest first. It posts as **`github-actions[bot]`**, not a `claude`-named
  user, so filtering by a "claude" login returns nothing. It may leave TWO
  comments (a "Reviewing…" stub plus a findings comment) or instead EDIT the
  stub in place minutes AFTER the check-run reports `success`, and a re-fired
  run creates a NEW comment even with `use_sticky_comment: true`. So gate a
  findings-poll on the body no longer matching "in progress" — never on a cached
  comment id, a length threshold, or the check-run conclusion.

- **A merged PR's CI status is not evidence the change was validated** — a PR
  merged mid-CI leaves a permanent `dbt Cloud: failure` that is a cancellation,
  not a build failure (mechanics in `.claude/context/dbt.md`).

- **`dagster-cloud-deploy / deploy` emits one same-named check-run per code
  location** (~5) — `get_check_runs` returns duplicates; wait for ALL to reach a
  terminal conclusion before calling the deploy green. A shared-library change
  (e.g. `libraries/dlt/`) redeploys every consuming location, not just the ones
  whose config you edited.

## dbt Cloud CI selection

## dbt Cloud CI builds only kipptaf

The dbt Cloud CI job (`Build - CI (Modified)`, dbt Cloud project 211862) runs
against the `kipptaf` project alone. A PR confined to a district project
(`kipp{newark,camden,miami,paterson}`) or a source-system package selects zero
models under `state:modified+` unless it changes a kipptaf-consumed `source()`
schema (column set) — so the dbt Cloud check goes green **trivially, not as
validation** (a ~30s no-op run). A dbt-only PR also gets NO branch deployment
(the `pull_request` paths in `.github/workflows/deploy-prod-*.yaml` exclude
`src/dbt/**`), so **nothing in CI builds those models** — a local `dbt build` is
the only pre-merge validation, and they are first exercised in prod after merge.
Never call such a PR CI-validated.

## dbt Cloud CI state comparison

`state:modified+` hashes every source node through `{{ target.name }}`
rendering. The CI job and the parse job in its `deferring_environment_id` must
share `target_name`, or every source with the target-conditional schema pattern
hash-mismatches and fans out to rebuild the whole graph.

Auto-retried CI runs invoke `dbt retry`, which replays the prior run's compiled
SQL. After fixing external state (defer relations, transient BQ errors), trigger
a fresh `dbt build` — don't rely on the retry.

## Editing a `sources-kipp*.yml` schema fans out `state:modified+`

Changing a source's schema (e.g. adding a `target=staging` branch) marks the
WHOLE source `state:modified` — CI's `state:modified+` builds EVERY kipptaf
model reading it, not just your target. A district model dropped from code but
lingering as a stale prod table is absent from the prod manifest → clone-skipped
→ its kipptaf consumer fails CI `Table not found`. Fix such frozen/retired
tables by declaring them a BQ-native source (`sources-bigquery.yml`, plain
hardcoded schema, no target branch) so kipptaf reads prod regardless of target.

## GitHub Actions on a PR

- `claude-code-review.yaml` — auto-reviews PRs touching `src/`, `tests/`,
  `scripts/`, `.github/workflows/` (excludes markdown). A PR editing a workflow
  runs that PR's own copy of it, so workflow changes review themselves. **Gated
  to `base=main` (`branches: [main]`)** — a **stacked PR** (base = another
  feature branch) gets no auto-review. dbt Cloud CI is NOT base-gated: it
  triggers via dbt Cloud's own GitHub app on PR events, independent of any
  GH-Actions `branches` filter, so a stacked PR **does** run dbt Cloud CI
  (verified on #4381) alongside Trunk + Dagster deploy — only
  `claude-code-review` is skipped. Review a stacked PR via
  `superpowers:requesting-code-review` or an `@claude` PR comment (`claude.yaml`
  is comment-triggered, not base-gated). A base-retarget after the parent merges
  does NOT re-fire `opened`, so `claude-code-review` does not auto-trigger then.

- **`claude-code-action` headless deadlock**: the action breaks its SDK loop on
  the FIRST result (`base-action/src/run-claude-sdk.ts`), so a run that
  dispatches background subagents ends with them orphaned and reports `success`
  having posted nothing (upstream #1462 / #1499, unfixed at v1.0.183; ~8-12% of
  fan-out runs). `Agent`, `Workflow`, `ScheduleWakeup`, `SendMessage` and
  `Monitor` are NOT gated by `--allowedTools` — deny them via
  `--disallowedTools` in `claude_args`. A second `--allowedTools` /
  `--disallowedTools` ACCUMULATES with the action's own list rather than
  replacing it (`parse-sdk-options.ts` `ACCUMULATING_FLAGS`), so adding tools
  cannot strip `update_claude_comment`.

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
  `deploy-prod-kipptaf.yaml` (verified: the commit touched 3 files, all `.md`,
  and a `kipptaf` run appeared for that headSha). This contradicts the
  pushed-delta model above, which predicts no run — one of the two is
  incomplete, and no mechanism is established here. Plan for the cost: a
  docs-only push to a PR is NOT free, so batch doc changes into the code commit
  rather than splitting them off to "avoid CI".

- **Each `deploy-prod-<location>.yaml` push-`paths` must list every dbt package
  in that district's `src/dbt/<district>/packages.yml`** (`src/dbt/pearson/**`,
  etc.). Drift silently skips that district's prod deploy on a shared
  source-package change, stranding it on stale code (PR #4175: paterson omitted
  `src/dbt/pearson/**` → failed contract enforcement while newark/camden
  deployed). After merging a source-package change, confirm every consuming
  district deployed (`gh run list --branch main`); a post-merge prod failure
  whose run tags show the OLD `dagster/git_commit_hash`/image is a
  missed/lagging deploy, not a code bug. The `pull_request` `paths`
  intentionally exclude `src/dbt/**` (dbt Cloud CI covers those); only the
  `push` section needs them.

- **The same push-`paths` drift hits shared Dagster library code**, not just dbt
  packages: `deploy-prod-<location>.yaml` must list every
  `src/teamster/libraries/<lib>/**` the location imports. A shared-library
  change (e.g. the Focus dlt fix #4216) silently skipped the kippmiami deploy
  because `src/teamster/libraries/dlt/**` was missing — only kipptaf, which
  listed it, deployed (fixed #4219). After merging a library change, confirm the
  consuming location actually **reloaded** before acting on the new code:
  `mcp__dagster__get_location_load_history` → newest entry `loadStatus: LOADED`
  with a matching `commit_hash`. A green Actions deploy job ≠ agent reloaded,
  and a missing push-path means it never deployed at all.
