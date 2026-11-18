# Dimension Error Tests (PR 4 of #5948) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every test on a `dim_*` model runs at `error` or is a unit test, and
no dimension carries a `relationships` test.

**Architecture:** Delete the 64 dim `relationships` tests and the 3
`_dbt_source_project` `accepted_values` tests on the IEP, ELL and meal dims.
Replace the one literal-only enum test (`dim_staff_cube_access.entity`) with a
unit test. Flip the rest to `error` with a
`kipptaf: marts: dimensions: +severity: error` block. The singular dim tests in
`tests/` sit outside that folder, so each gets an explicit `severity`. No model
SQL changes.

**Tech Stack:** dbt (BigQuery), kipptaf project.

**Spec:** `docs/superpowers/specs/2026-10-15-mart-test-rule.md` and the sorting
rule in `.claude/rules/dbt-yaml.md` → _Test config defaults_. Precedents:
bridges #5960, facts #5973
(`docs/superpowers/plans/2026-10-16-fact-error-tests.md`).

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/cbini/test/claude-dim-error-tests`,
  branch `cbini/test/claude-dim-error-tests`. Use `git -C <worktree>` and
  absolute paths. Always `uv run`. Stage with `git add -u` (plus explicit new
  paths).
- dbt commands run from `src/dbt/kipptaf` in the worktree. Prod-deferred form:
  `uv run dbt <cmd> --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod`.
  Select dims with `path:models/marts/dimensions`, not a `dim_*` glob.
- Keep every `constraints:` `foreign_key` block and every
  `config.meta.foreign_key` block. Delete only the tests this plan names.
- Do not touch tests on any model outside `models/marts/dimensions/`, except the
  dim singular tests in `tests/properties.yml`.
- A grain test that fails in prod on a source defect gets `severity: warn` plus
  a `TODO(#N)` comment naming an open issue; the folder still flips.
- PR body: `Refs #5948` (no `Closes`). No PII in commits or the PR; counts only.
- Lint before push:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  from inside the worktree.

## Settled decisions this plan rests on

- Kept at `error`, by the rule's categories:
  - Grain: every `unique`, `not_null`, the 2 `unique_combination_of_columns`
    (`dim_school_calendars`, `dim_staff_reporting_chain`), and the 5 span or
    overlap singulars.
  - Source data gates on `dim_staff_cube_access`: the 5 `expression_is_true`
    tests (2 now `warn`, 3 already `error`) and the 7 `accepted_values` on
    `student_location_scope` and the 6 `staff_*_scope` columns. The SQL
    `coalesce`s Google Sheet values into those 7, so a sheet typo reaches the
    column; no unit test can stand in.
  - Model invariants: `effective_start <= effective_end` on
    `dim_staff_reporting_periods` and `dim_work_assignment_primary`, and
    `test_dim_regions_business_unit_code_coverage`.
- Replaced by a unit test: `dim_staff_cube_access.entity` `accepted_values`. The
  `case` in `current_assignment` and the `'unknown'` literal in `access_spine`
  are its only sources, so only a code change can break it.
- Deleted as an upstream promise: the 3 `_dbt_source_project` `accepted_values`
  on `dim_student_iep_status`, `dim_student_ell_status`,
  `dim_student_meal_eligibility_status`.
- `dim_student_iep_status__no_overlapping_spans` and
  `dim_student_meal_eligibility_status__no_overlapping_spans` already carry
  `severity: warn` with an Ops note. Task 1 decides whether they stay `warn`.

## Review Focus

- A column whose only test was deleted must not keep an empty `data_tests:` key.
  Delete the key.
- `test_miami_section_enrollment_orphan_rate` and
  `test_miami_section_enrollment_dropped_rate` attach to
  `dim_student_section_enrollments` but are source-data rate monitors at `warn`.
  They are out of scope; leave them alone and say so in the PR.
- The unit test must mock every `ref()` in `dim_staff_cube_access.sql` (13
  inputs), or dbt fails to compile it.
- A `warn` grain test needs an open issue in its `TODO(#N)`. A closed or missing
  issue means file one first.
- `dbt ls` on the singular tests must resolve each to the severity this plan
  sets, because the folder block does not reach them.

---

### Task 1: Inventory and prod check

**Interfaces:**

- Produces: `<scratchpad>/dim-tests-main.txt` (sorted test node names on main)
  and a pass/fail list per dim test in prod. Task 3 reads the failures.

- [ ] **Step 1: Parse main fresh and save the dim test list**

`git worktree add --detach <scratchpad>/main-parse origin/main`, run
`uv run dbt parse --no-partial-parse` in its `src/dbt/kipptaf`, and write the
sorted test node names whose `attached_node` path starts with
`marts/dimensions`, plus the 6 dim singulars in `tests/`, to
`<scratchpad>/dim-tests-main.txt`. Expected: 64 names starting `relationships_`;
the rest are the grain, gate and invariant tests above.

- [ ] **Step 2: Run every dim test against prod**

`uv run dbt test --select path:models/marts/dimensions <prod-deferred flags> 2>&1 | tail -n 40`,
then the 6 singulars by name. Record each `WARN`/`FAIL` with its count.
Expected: `relationships_*` failures may appear (they are deleted next). Every
non-`relationships` failure goes to Task 3 Step 3.

No commit.

### Task 2: Delete the out-of-scope tests

**Files:**

- Modify: every `src/dbt/kipptaf/models/marts/dimensions/properties/dim_*.yml`
  with a `relationships` entry
- Modify: `dim_student_iep_status.yml`, `dim_student_ell_status.yml`,
  `dim_student_meal_eligibility_status.yml` (`_dbt_source_project`
  `accepted_values`)

**Interfaces:**

- Consumes: `<scratchpad>/dim-tests-main.txt`.
- Produces: the dim test set with 67 fewer nodes. Task 3 flips the remainder.

- [ ] **Step 1: Delete every `- relationships:` item and the 3
      `_dbt_source_project` `accepted_values` items**

Remove each item with its `arguments:` and `config:` children. Delete any
`data_tests:` key left empty.

- [ ] **Step 2: Diff the parsed nodes**

Parse the worktree with `--no-partial-parse`, write the same list to
`<scratchpad>/dim-tests-branch.txt`, `comm -23` main against branch. Expected:
exactly 67 removed (64 `relationships_*`, 3
`accepted_values_*_dbt_source_project*`), 0 added.

- [ ] **Step 3: Commit**

`test(dbt): delete dimension relationships and upstream-promise tests`, body
naming both counts.

### Task 3: Unit test for `entity`, then flip dimensions to `error`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_cube_access.yml`
  (`unit_tests:` block; drop `entity` `accepted_values`, keep its `not_null`)
- Modify: `src/dbt/kipptaf/dbt_project.yml` (`data_tests:` block, after
  `facts:`)
- Modify: `src/dbt/kipptaf/tests/properties.yml` (6 dim singulars)

**Interfaces:**

- Consumes: Task 1's prod failures; Task 2's remaining tests.

- [ ] **Step 1: Write the unit test**

`test_dim_staff_cube_access_entity_from_business_unit`, model
`dim_staff_cube_access`. Given three current, primary staff whose home org unit
carries `business_unit_code` `KIPP_TAF`, a regional code, and a code
`dim_regions` does not hold. `dim_regions` holds `KIPP_TAF` and the regional
code. Every other `ref()` is `rows: []`. Expect `entity` `KTAF`, `Region`,
`unknown` by `staff_key`, with `student_location_scope` `none` for all three (no
role row).

- [ ] **Step 2: Run it**

`uv run dbt test --select test_dim_staff_cube_access_entity_from_business_unit <prod-deferred flags> 2>&1 | tail -n 15`.
Expected: PASS. Then change `'KTAF'` to `'KTAFX'` in the SQL `case`, re-run, see
FAIL, and revert the SQL (`git -C <worktree> diff --stat` shows only YAML).

- [ ] **Step 3: Set severities**

Add `dimensions: +severity: error` beside `bridges:` and `facts:`. In
`tests/properties.yml`, give the 4 singulars without `severity` an explicit
`severity: error`. For each test Task 1 found failing:

- grain or gate failing on a source defect: `severity: warn` with
  `# TODO(#N): <one line>` on the line above, N an open issue (file one with
  counts only if none exists);
- the IEP and meal span tests: if they now pass, set `error` and drop the
  "Restore severity" sentence; if not, keep `warn` and replace the sentence with
  a `TODO(#N)`.

- [ ] **Step 4: Check resolved severity**

`uv run dbt ls --resource-type test --select path:models/marts/dimensions --output json --output-keys "name config" | grep '^{'`
plus the 6 singulars by name, count by `config.severity`. Expected: every test
`error` except the ones Step 3 set to `warn`, each of which has a `TODO(#N)`.

- [ ] **Step 5: Run the dim suite against prod**

`uv run dbt test --select path:models/marts/dimensions <prod-deferred flags> 2>&1 | tail -n 15`
plus the 6 singulars. Expected: `ERROR=0`; `WARN` equals the Step 3 `warn`
count.

- [ ] **Step 6: Lint and commit**

Trunk check every changed file. Commit
`test(dbt): run dimension tests at error severity`.

### Task 4: Ship

- [ ] **Step 1: Push and open the PR**

Body from `.github/pull_request_template.md`: `Refs #5948`, the Task 2 counts,
the Task 3 Step 3 `warn` list with issue links, the out-of-scope Miami rate
tests, and the caveat that an `error` dim test alarms after dbt writes the
table, so Cube can still read a bad dim. Read the body back after creating it.
