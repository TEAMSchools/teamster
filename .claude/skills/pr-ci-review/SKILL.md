---
name: pr-ci-review
description:
  "Use when opening, monitoring, or responding to review on a pull request in
  this repo: reading claude-review bot findings, checking dbt Cloud CI state
  before pushing fixes, fetching CI warnings, telling commit statuses from check
  runs, dagster-cloud-deploy check-runs, re-triggering claude-review via draft
  toggle, and the not_planned/Asana handoff convention."
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
