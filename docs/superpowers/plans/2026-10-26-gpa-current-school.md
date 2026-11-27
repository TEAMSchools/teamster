# GPA Filed Under the Current School Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** File each student-year's GPA under the student's current school, and
stop the GPA snapshot from keeping stale rows.

**Architecture:** The package model `int_powerschool__gpa_term` takes `schoolid`
from the student's latest stint that year (`rn_year = 1`), falling back to the
credit-hour school. `fct_grades_gpa` joins only that stint. The snapshot closes
rows whose key leaves the source, and the lookback drops `schoolid` from its
grain so a label change cannot split or blank a student's history.

**Tech Stack:** dbt (BigQuery), dbt unit tests, dbt Cloud CI.

**Spec:** `docs/superpowers/specs/2026-10-26-gpa-current-school-design.md`

## Global Constraints

- Branch `cbini/fix/claude-gpa-term-school-grain`, worktree
  `/workspaces/teamster/.claude/worktrees/cbini/fix/claude-gpa-term-school-grain`.
  Every path below is relative to it. PR #5531.
- Always `uv run dbt ...`. Local builds use `--target dev` only.
- Any `--target staging` write (Task 5) needs the user's authorization in the
  turn right before it, in its own Bash call.
- Never `--full-refresh` the snapshot. Never run warehouse DDL/DML.
- No PII values in commits, PR text or comments: aggregates only.
- `grade_rollup` (which courses count) stays as is. The merge waits on the Asana
  decision task 1218882662777658.
- Commit with `git add -u` (plus new files by name); end messages with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Before pushing, run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  on every touched SQL, YAML and markdown file.

## Review Focus

1. **A partial source run mass-closes snapshot rows.** With
   `hard_deletes: invalidate`, a run where a district's
   `int_powerschool__gpa_term` is empty closes every row for that district.
   Expected: no such run. Task 3 checks that the snapshot's source is the
   kipptaf union of all districts and records the risk in the snapshot YAML
   comment.
2. **Transfer students mid-year in `int_topline__gpa_term_weekly`.** It joins
   the snapshot on the week's enrollment `schoolid`, so weeks at the first
   school find no GPA row. That was already true for one of the two schools
   before this change. Out of scope; Task 6 measures it and the PR body names
   it.
3. **Lookback at boundaries before rollout.** Two rows (old label and new label)
   can both be valid at a past boundary. Expected: the newer version wins.
   Pinned by the Task 4 unit test.
4. **Student with grades but no stint that year.** Expected: `schoolid` falls
   back to the credit-hour school, and `fct_grades_gpa` drops the row (no stint
   to join, same as today). Pinned by the Task 1 unit test.
5. **Two stints at one school in one year.** Expected: one `fct_grades_gpa` row
   per term, keyed to the later stint's `entrydate`. Pinned by the Task 2 unit
   test.

---

### Task 1: Current school in `int_powerschool__gpa_term`

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_term.sql`
  (`school_credits` / `gpa_calcs` CTEs, lines 78-156)
- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_term.yml`
  (model + `schoolid` descriptions, new `unit_tests:` block)
- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gpa_term.yml`
  (model + `schoolid` descriptions)
- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa.yml`
  (model description)
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__gpa_term.yml`
  (model description: "the school with the most credit hours" becomes "the
  student's current school that year")

**Interfaces:**

- Consumes: `base_powerschool__student_enrollments` (`studentid`, `yearid`,
  `schoolid`, `rn_year`). Precedent for the join:
  `int_powerschool__gpa_cumulative.sql:96-101`.
- Produces: `int_powerschool__gpa_term.schoolid` = current school. Columns and
  grain are unchanged.

- [ ] **Step 1: Write the failing unit test**
      `int_powerschool__gpa_term__files_under_current_school` in the package
      YAML. Override `current_academic_year: 2025`. Mock with `format: sql`:
  - `base_powerschool__final_grades`: yearid 35, storecode `Q1`,
    `exclude_from_gpa = 0`, `termbin_is_current = true`. Student 1 has 2 rows at
    school 100 (credit hours 1.0 each) and 1 row at school 200 (1.0). Student 2
    has 1 row at school 100 (1.0).
  - `base_powerschool__student_enrollments`: student 1, yearid 35, school 200,
    `rn_year = 1`, plus school 100 with `rn_year = 2`. No rows for student 2.
  - `stg_powerschool__storedgrades`: 1 row with `storecode = 'Q1'`, so the Y1
    filter drops it. `stg_powerschool__courses` and
    `int_powerschool__gradescaleitem_lookup`: 1 unrelated row each.
  - `stg_powerschool__students`: ids 1 and 2. `stg_powerschool__schools`: 100
    and 200.
  - Expect (columns `studentid, schoolid, yearid, term_name`):
    `(1, 200, 35, Q1)` and `(2, 100, 35, Q1)`. Student 1 would get 100 under the
    credit-hour rule, so the test fails today.

- [ ] **Step 2: Run it and confirm it fails**

  Run:
  `uv run dbt test --select "int_powerschool__gpa_term,test_type:unit" --project-dir src/dbt/kippnewark --target dev 2>&1 | tail -n 30`
  Expected: FAIL, with `schoolid` 100 where 200 was expected for student 1.

- [ ] **Step 3: Implement.** Add a CTE `current_school` (`studentid`, `yearid`,
      `schoolid` from
      `base_powerschool__student_enrollments where rn_year = 1`). In
      `gpa_calcs`, left join it on `studentid` and `yearid` and select
      `coalesce(cs.schoolid, sc.schoolid) as schoolid` in place of
      `sc.schoolid`. Keep the `school_credits` inner join as the fallback. Add
      no comments to the SQL; the description carries the rule.

- [ ] **Step 4: Update descriptions.** Both `int_powerschool__gpa_term.yml`
      `schoolid` entries: "The student's current school that year: the school of
      their latest enrollment that year. When the student has GPA grades but no
      enrollment that year, the school with the most potential GPA credit hours,
      ties broken by the higher school number. A label for the row, not a join
      key." Fix the model description and the two related model descriptions
      listed under Files to match. No issue refs in descriptions.

- [ ] **Step 5: Run the test and the model build**

  Run:
  `uv run dbt build --select int_powerschool__gpa_term+1 --project-dir src/dbt/kippnewark --target dev 2>&1 | tail -n 30`
  Expected: the unit test passes, the model builds, both uniqueness tests pass.
  Repeat with `--project-dir src/dbt/kippcamden` and `src/dbt/kipppaterson`.

- [ ] **Step 6: Commit**
      `fix(powerschool): file term GPA under the student's current school`.

### Task 2: `fct_grades_gpa` joins only the latest stint

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_grades_gpa.sql` (CTE
  `student_enrollments`, lines 2-11)
- Modify: `src/dbt/kipptaf/models/marts/facts/properties/fct_grades_gpa.yml`
  (new `unit_tests:` block)

**Interfaces:**

- Consumes: `int_students__student_enrollment_union.rn_year` (present on both
  the PowerSchool and Focus branches).
- Produces: one row per student, year and term, keyed to the latest stint.

- [ ] **Step 1: Write the failing unit test**
      `fct_grades_gpa__one_row_per_term_for_two_stints`. Mock with
      `format: sql`:
  - `int_students__student_enrollment_union`: student number 8400001,
    `_dbt_source_project = 'kippnewark'`, academic year 2025, school 200, two
    stints: entry `2024-09-01` with `rn_year = 2`, and entry `2025-01-15` with
    `rn_year = 1`.
  - `int_students__gpa_term`: one Q1 row for that student, school 200,
    yearid 35.
  - `int_students__gpa_cumulative`: one matching row with `studentid` not null.
  - `stg_google_sheets__reporting__terms`: no matching row (`type = 'RT'`,
    another school).
  - Expect exactly 1 row, with `student_enrollment_key` built from the
    `2025-01-15` stint. Assert `academic_year`, `gpa_term`, `is_current` too.
    Today the test returns 2 rows.

- [ ] **Step 2: Run it and confirm it fails**

  Run:
  `uv run dbt test --select "fct_grades_gpa,test_type:unit" --project-dir src/dbt/kipptaf --target dev 2>&1 | tail -n 30`
  Expected: FAIL, 2 rows where 1 was expected.

- [ ] **Step 3: Implement.** Add `where rn_year = 1` to the
      `student_enrollments` CTE. Nothing else changes in the join. If
      `dbt-layer-check` flags the `= 1` filter as A5, the pick is the business
      rule: add `standard_exempt: {A5: latest stint owns the student-year GPA}`
      in the model YAML.

- [ ] **Step 4: Run the test** (same command). Expected: PASS.

- [ ] **Step 5: Commit** `fix(dbt): key fct_grades_gpa to the latest stint`.

### Task 3: Snapshot closes stale rows

**Files:**

- Modify: `src/dbt/kipptaf/snapshots/powerschool.yml`
  (`snapshot_powerschool__gpa_term` config, lines 41-78)

**Interfaces:**

- Produces: at most one current row per
  `_dbt_source_relation, studentid, yearid` once the first post-deploy run
  completes.

- [ ] **Step 1: Confirm the source covers every district.** Read
      `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gpa_term_current.sql`
      and its upstream union wrapper. Confirm it unions all district relations
      in one model. Record the result in the PR body.

- [ ] **Step 2: Add `hard_deletes: invalidate`** under `config:`, after
      `check_cols`. Add a two-line YAML comment above it: a run where a
      district's source is empty closes all of that district's rows, and the
      next good run reopens them as new versions. Do not add any DDL;
      `invalidate` uses no new columns.

- [ ] **Step 3: Parse**

  Run:
  `uv run dbt parse --no-partial-parse --project-dir src/dbt/kipptaf 2>&1 | tail -n 5`
  Expected: no errors.

- [ ] **Step 4: Commit**
      `fix(dbt): close stale rows in snapshot_powerschool__gpa_term`.

### Task 4: Lookback drops `schoolid` from its grain

**Files:**

- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gpa_term_lookback.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gpa_term_lookback.yml`
  (grain test, description, `schoolid` column entry, unit test)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql:270-274`
  (drop `and enr.schoolid = lb.schoolid`)

**Interfaces:**

- Produces: `int_powerschool__gpa_term_lookback` at grain
  `_dbt_source_relation, studentid` (current year only), columns as today minus
  `schoolid`.

- [ ] **Step 1: Extend the unit test.** In
      `unit_gpa_term_lookback_as_of_boundaries`, drop `schoolid` from every
      `expect` row. Add student 4: two versions both valid across all three
      boundaries, school 101 with `dbt_valid_from` 40 days ago and `gpa_y1` 2.0,
      and school 102 with `dbt_valid_from` 35 days ago and `gpa_y1` 3.0, both
      `dbt_valid_to` `9999-12-31`. Expect one row for student 4 with 3.0 at all
      three horizons.

- [ ] **Step 2: Run it and confirm it fails**

  Run:
  `uv run dbt test --select "int_powerschool__gpa_term_lookback,test_type:unit" --project-dir src/dbt/kipptaf --target dev 2>&1 | tail -n 30`
  Expected: FAIL (two rows for student 4, and a `schoolid` column mismatch).

- [ ] **Step 3: Implement.** In `matched`, drop `schoolid` and add
      `row_number() over (partition by _dbt_source_relation, studentid, yearid, days_prior order by dbt_valid_from desc) as rn_version`.
      Add a CTE that keeps `rn_version = 1`, then aggregate it, grouped by
      `_dbt_source_relation, studentid, yearid`. This is a source `int_`, so the
      pick is allowed under A5.

- [ ] **Step 4: Update the YAML.** Grain test columns become
      `_dbt_source_relation, studentid`. Remove the `schoolid` column entry.
      Rewrite the description: one row per student for the current year; the
      snapshot closes rows that leave the source; when two versions overlap a
      boundary, the newer one wins. Remove the sentence saying check snapshots
      never close rows.

- [ ] **Step 5: Update the consumer.** Remove the `enr.schoolid = lb.schoolid`
      predicate in `rpt_tableau__student_course_grades.sql`.

- [ ] **Step 6: Run tests and build**

  Run:
  `uv run dbt build --select int_powerschool__gpa_term_lookback rpt_tableau__student_course_grades --project-dir src/dbt/kipptaf --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 30`
  Expected: unit test, grain test and the `rpt_` grain test pass. Read the
  `dbt-local-dev` skill before this run for the `--defer` traps.

- [ ] **Step 7: Commit**
      `fix(dbt): key the GPA lookback on student, not school`.

### Task 5: Seed CI and push

The kipptaf union wrapper over `int_powerschool__gpa_term` is unmodified, so CI
reads the old prod values through `zz_stg_kipptaf` and the
`rpt_tableau__gradebook_gpa` grain test keeps failing.

- [ ] **Step 1: Lint** every touched file (Global Constraints command). Fix lint
      findings; leave formatting to the commit hook.

- [ ] **Step 2: Ask the user** for authorization to run, each in its own Bash
      call:
  - `uv run dbt build --select int_powerschool__gpa_term --project-dir src/dbt/<district> --target staging`
    for `kippnewark`, `kippcamden` and `kipppaterson`.
  - `uv run dbt build --select int_powerschool__gpa_term --project-dir src/dbt/kipptaf --target staging`
    (the wrapper, so `zz_stg_kipptaf` reads the rebuilt district copies).

  Run them only after the user says yes, restating the consent in the message
  before each call.

- [ ] **Step 3: Push** the branch (spec, plan and code together). Comment the
      spec's branch URL on #6126.

- [ ] **Step 4: Watch CI** with a Monitor (per `pr-ci-review`). Process the
      `claude-review` findings when they post, and post per-finding verdicts.

### Task 6: Measure and update the PR body

- [ ] **Step 1: Before-and-after counts** through the BigQuery MCP, aggregates
      only. Before is prod; after is the dev build from Tasks 1-2.
  - `fct_grades_gpa`: rows per student, year and term greater than 1.
  - `int_powerschool__gpa_term`: rows whose `schoolid` changed, by district and
    year.
  - Snapshot: student-years with more than one current row (baseline 431; target
    0 after the first post-deploy run, which is checked post-merge).
  - `int_topline__gpa_term_weekly`: enrolled weeks with a null `gpa_y1`, current
    year (Review Focus 2).

- [ ] **Step 2: Update the PR #5531 body** from
      `.github/pull_request_template.md`: `Closes #6126`, `Refs #4938`, the
      counts, the Asana merge gate, and the post-merge check (snapshot
      current-row count reaches 0 after its next 23:00 run).
