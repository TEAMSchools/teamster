# Fact Error Tests (PR 3 of #5948) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every test on a `fct_*` model runs at `error`, and no fact carries a
`relationships` test.

**Architecture:** Delete the 80 fact `relationships` tests. Keep the other 33
tests, which already pass in prod, and flip them to `error` with a
`kipptaf: marts: facts: +severity: error` block. The one singular fact test
lives in `tests/`, outside that folder, so it gets an explicit
`severity: error`. No model SQL changes.

**Tech Stack:** dbt (BigQuery), kipptaf project.

**Spec:** `docs/superpowers/specs/2026-10-15-mart-test-rule.md` and the sorting
rule in `.claude/rules/dbt-yaml.md` → _Test config defaults_. Bridges precedent:
PR #5960.

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/cbini/test/claude-fact-error-tests`,
  branch `cbini/test/claude-fact-error-tests`. Use `git -C <worktree>` and
  absolute paths. Always `uv run`. Stage with `git add -u` (plus explicit new
  paths).
- dbt commands run from `src/dbt/kipptaf` in the worktree. Prod-deferred form:
  `uv run dbt <cmd> --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod`.
  Run `uv run dbt deps` first if `dbt_packages/` is missing.
- Keep every `constraints:` `foreign_key` block and every
  `config.meta.foreign_key` block. Delete only `relationships` entries.
- Do not touch tests on any model outside `models/marts/facts/`.
- PR body: `Refs #5948` (no `Closes`). No PII in commits or the PR; counts only.
- Lint before push:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  from inside the worktree.

## Prod findings this plan rests on (2026-10-16)

- Last prod run of all 113 fact tests: 111 pass, 2 warn.
- `fct_grades_category.student_section_enrollment_key`: 100 orphans, 5 Newark
  AY2026 sections. Cause is build timing. `int_students__category_grades` (daily
  table build) still holds sections that `int_students__course_enrollments`
  (intraday build) dropped after PowerSchool deleted the `cc` rows. The fact
  reads `int_students__course_enrollments` through an inner join, so the fact's
  keys are a subset of the dim's at build time. Rule: build timing → delete. No
  upstream test or defense needed.
- `fct_grades_term` `unique`: 46 duplicate keys. #5970 fixes this. It merged
  2026-10-16 17:00 UTC, but `int_students__final_grades` last built at 08:04
  UTC, so prod does not have the fix yet. Task 3 gates on it.
- No fact test carries an explicit `severity: warn`, `warn_if`, or `error_if`,
  so the folder block reaches all 32 remaining generic tests.

## Review Focus

- A column whose only test was a `relationships` test must not be left with an
  empty `data_tests:` key. Delete the key.
- `fct_student_attendance_enrollment_daily.student_enrollment_key` and similar
  columns carry `config.meta.foreign_key`. That block stays.
- The singular test must resolve to `error` in `dbt ls`. The folder block does
  not reach it.
- `fct_grades_term` `unique` must pass on post-#5970 data before the PR merges,
  or every Dagster run of the fact fails.
- The `accepted_values` + `not_null` pair on
  `fct_assessment_scores_enrollment_scoped.response_type` must both survive.

---

### Task 1: Delete the fact `relationships` tests

**Files:**

- Modify: every `src/dbt/kipptaf/models/marts/facts/properties/fct_*.yml` that
  has a `relationships` entry
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_student_attendance_enrollment_periods.yml`
  (`student_enrollment_key` description)

**Interfaces:**

- Produces: 33 fact test nodes, none of type `relationships`. Task 2 flips them.

- [ ] **Step 1: Parse main fresh and save the test node list**

Make a temp checkout of main
(`git worktree add --detach <scratchpad>/main-parse origin/main`), run
`uv run dbt parse --no-partial-parse` in its `src/dbt/kipptaf`, and write the
sorted `resource_type == 'test'` node names whose `attached_node` or `refs`
include a `fct_` model to `<scratchpad>/fact-tests-main.txt`. Expected: 113
names.

- [ ] **Step 2: Delete every `- relationships:` list item under facts**

Remove each item with its `arguments:` and `config:` children. Where a column's
`data_tests:` list becomes empty, delete the `data_tests:` key. Do it with a
short ruamel-free line script or by hand; check the result parses
(`uv run dbt parse --no-partial-parse` succeeds).

- [ ] **Step 3: Cut the dated measurement from `student_enrollment_key`**

In `fct_student_attendance_enrollment_periods.yml`, replace the sentence
starting "Measured against this fact's rows…" through "…rather than exposed."
with: "A stint absent from dim_student_enrollments resolves a null location,
which hides the row from a location-scoped viewer rather than exposing it."

- [ ] **Step 4: Diff the parsed nodes**

Parse the worktree with `--no-partial-parse`, write the same list to
`<scratchpad>/fact-tests-branch.txt`, and `comm -23` main against branch.
Expected: exactly 80 removed names, every one starting `relationships_`; 0
added; 33 remaining.

- [ ] **Step 5: Commit**

`test(dbt): delete fact relationships tests` with a body naming the count and
the build-timing finding for `fct_grades_category` (counts only).

### Task 2: Flip facts to `error`

**Files:**

- Modify: `src/dbt/kipptaf/dbt_project.yml` (`data_tests:` block, after
  `bridges:`)
- Modify: `src/dbt/kipptaf/tests/properties.yml`
  (`fct_assessment_scores_enrollment_scoped__term_covers_assessment_date`
  `config:`)

**Interfaces:**

- Consumes: the 33 test nodes from Task 1.

- [ ] **Step 1: Check resolved severity before the change**

`uv run dbt ls --resource-type test --select "fct_*" --output json --output-keys "name config" | grep '^{'`
→ count by `config.severity`. Expected: 2 `ERROR`, 31 `warn` (the two
`expression_is_true` tests already set `error`).

- [ ] **Step 2: Add the folder block and the singular test's severity**

```yaml
kipptaf:
  marts:
    bridges:
      +severity: error
    facts:
      +severity: error
```

In `tests/properties.yml`, add `severity: error` under the singular test's
existing `config:` (beside `meta:`).

- [ ] **Step 3: Re-run the severity check**

Same command as Step 1, plus the singular test by name. Expected: all 33 resolve
to `error` (case-insensitive), 0 `warn`.

- [ ] **Step 4: Commit**

`test(dbt): run fact tests at error severity`.

### Task 3: Prove every remaining fact test passes in prod

**Interfaces:**

- Consumes: the 33 `error` tests from Task 2.

- [ ] **Step 1: Check whether #5970 has reached prod**

```sql
select table_id, timestamp_millis(last_modified_time) as built
from `teamster-332318.kipptaf_students.__TABLES__`
where table_id = 'int_students__final_grades'
```

Expected: `built` after `2026-10-16 17:00:00 UTC`. If not, do Step 2b instead of
Step 2.

- [ ] **Step 2: Run the fact tests against prod**

`uv run dbt test --select "fct_*" <prod-deferred flags> 2>&1 | tail -n 15`
Expected: `PASS=33 WARN=0 ERROR=0`.

- [ ] **Step 2b (only if #5970 is not in prod yet)**

`uv run dbt build --select int_students__final_grades fct_grades_term <prod-deferred flags> 2>&1 | tail -n 15`
then the Step 2 command with `--exclude fct_grades_term`, and
`uv run dbt test --select fct_grades_term --target dev` against the dev build.
Expected: all pass. Record in the ledger that the prod check for
`fct_grades_term` is still owed, and re-run Step 1 + Step 2 before the PR is
marked ready to merge.

- [ ] **Step 3: Run the fact unit tests**

`uv run dbt test --select "test_type:unit,marts.facts" <prod-deferred flags> 2>&1 | tail -n 10`
Expected: all pass (nothing in this PR touches them; this is the suite).

No commit; this task only verifies.

### Task 4: Record the grain fallback in the rule

**Files:**

- Modify: `.claude/rules/dbt-yaml.md` (_Test config defaults_, the "Grain:"
  sub-bullet)

- [ ] **Step 1: Add one sentence to the "Grain:" sub-bullet**

"If a grain test fails in prod on a source defect that waits on a fix elsewhere,
set `severity: warn` on that one test with a `TODO(#N)` comment, and still flip
the folder."

- [ ] **Step 2: Lint every changed file**

`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <changed files> </dev/null`
Expected: no lint findings (formatting is left to the hook).

- [ ] **Step 3: Commit**

`docs(claude): add the grain-test fallback to the mart test rule`.

### Task 5: Ship

- [ ] **Step 1: Record the deferred population check on #5948**

Comment on #5948: the attendance facts hash `student_enrollment_key` from
`int_extracts__student_enrollments`, and `dim_student_enrollments` hashes it
from `int_students__student_enrollment_union`. The gap is 0 today. The
`relationships` tests that watched it are gone; the shared-upstream or unit test
fix stays tracked on #5948 for the dimensions PR, which owns
`dim_student_enrollments`.

- [ ] **Step 2: Push and open the PR**

Body from `.github/pull_request_template.md`, `Refs #5948`, counts from Task 1
Step 4, the two prod findings above, and the Task 3 result. Read the body back
after creating it.
