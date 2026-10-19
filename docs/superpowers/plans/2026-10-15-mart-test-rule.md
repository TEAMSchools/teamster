# Mart Test Rule (PR 1 of #5948) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write the "marts and `rpt_` models carry only error-level tests" rule
into the dbt YAML conventions, and delete the four `relationships` tests that
measure build timing instead of data.

**Architecture:** One convention edit in `.claude/rules/dbt-yaml.md`, four test
deletions in mart properties YAML. No model SQL changes, no severity flips. The
`foreign_key` constraints on the same columns stay, so the marts reference
diagram is unchanged.

**Tech Stack:** dbt (BigQuery), kipptaf project.

**Spec:** #5948 design comment
(<https://github.com/TEAMSchools/teamster/issues/5948#issuecomment-6202532128>).
Issue: #5952.

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/cbini/refactor/claude-mart-test-rule`.
  Use `git -C <worktree>` and absolute paths on every call. Always `uv run`.
- Change no test severity in this PR. Folder flips come in PRs 2–6.
- Keep every `constraints:` `foreign_key` block. Delete only the
  `data_tests: - relationships:` entry.
- Lint before push:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  from inside the worktree.

## Review Focus

- A deleted test's sibling tests on the same column (`not_null`) must survive.
  Check the YAML list still parses as a list, not an empty `data_tests:` key.
- `fct_student_attendance_enrollment_daily` carries `warn_if: ">2286"` inside
  the test being deleted. Confirm no other `warn_if` on that model changed.
- The convention text must not contradict the staging bullet just above it
  (staging tests stay `severity: error`).

---

### Task 1: Delete the build-timing `relationships` tests

These tests compare a fact's key to a dim built at a different time. Their
orphans come and go with rebuild order; all four returned 0 orphans in prod on
2026-10-15.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_student_attendance_enrollment_daily.yml`
  (`student_enrollment_key`, test at ~line 141, includes `warn_if: ">2286"`)
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_student_attendance_enrollment_periods.yml`
  (`student_enrollment_key`, ~line 148)
- Modify:
  `src/dbt/kipptaf/models/marts/bridges/properties/bridge_survey_expectations.yml`
  (`student_enrollment_key`, ~line 84)
- Modify: `src/dbt/kipptaf/models/marts/facts/properties/fct_grades_term.yml`
  (`student_section_enrollment_key`, ~line 34)

`fct_grades_term` and `dim_student_section_enrollments` are both views, so the
lag sits one layer up: `int_students__final_grades` and
`int_students__course_enrollments` are tables built at different times. If the
implementer finds evidence the orphans are a population mismatch instead, stop
and report rather than delete.

`fct_student_attendance_streaks` and `fct_student_attendance_interventions`
carry the same test but never warned; they are sorted in the facts PR.

- [ ] **Step 1: Read each file and delete only the `- relationships:` entry**
      (with its `arguments`/`config` children) under the named column. If it was
      the column's only test, remove the empty `data_tests:` key too.

- [ ] **Step 2: Verify the tests are gone and nothing else moved**

  Run from the worktree:
  `uv run dbt parse --project-dir src/dbt/kipptaf 2>&1 | tail -n 5` Expected:
  parse succeeds.

  Then:
  `jq -r '.nodes[] | select(.resource_type=="test" and (.name|startswith("relationships_")) and (.attached_node // "" | test("fct_student_attendance_enrollment_(daily|periods)|fct_grades_term|bridge_survey_expectations")) and (.column_name|test("^student_(section_)?enrollment_key$"))) | .name' src/dbt/kipptaf/target/manifest.json`
  Expected: no output.

  `git -C <worktree> diff --stat` shows exactly the four YAML files, deletions
  only.

- [ ] **Step 3: Lint the four files** with the trunk command above. Expected: no
      issues.

- [ ] **Step 4: Commit**

  ```bash
  git -C <worktree> add -u
  git -C <worktree> commit -m "test(dbt): drop build-timing relationships tests on marts"
  ```

### Task 2: Write the rule into the dbt YAML conventions

**Files:**

- Modify: `.claude/rules/dbt-yaml.md`, _Test config defaults_, the sentence
  "Intermediate/mart/`rpt_` tests may omit the override where a warning is
  acceptable." (~lines 281–282)

- [ ] **Step 1: Replace that sentence** with "Intermediate tests may omit the
      override where a warning is acceptable." and add one new bullet after the
      staging bullet. The bullet carries, in the file's existing terse style:

  - Marts and `rpt_` models carry only `error` tests and unit tests. Rollout is
    per folder (#5948); until a folder flips, new tests there set
    `config: severity: error` explicitly.
  - Backstop: the grain test on every mart and `rpt_` model, plus `not_null` on
    natural-key grain columns (`unique` skips nulls). Surrogate PKs get `unique`
    only.
  - Everything else sorts: model logic → unit test; an upstream promise →
    `error` on the model that makes it; source data → the earliest model that
    sees it, either `warn` (actionable description: source system, what is
    wrong, what to change) with a downstream defense, or an `error` gate; build
    timing → delete.
  - A gate lands as `warn` first and flips after it passes in prod. Skipping
    protects only tables; check views between the gate and consumers.

  Keep it under 15 lines. Per `.claude/rules/claude-md-editing.md`, each line
  must change a decision; drop any that does not.

- [ ] **Step 2: Lint** `.claude/rules/dbt-yaml.md` with the trunk command.
      Expected: no issues.

- [ ] **Step 3: Commit**

  ```bash
  git -C <worktree> add -u
  git -C <worktree> commit -m "docs(dbt): marts and rpt_ models carry only error tests"
  ```

### Task 3: Ship

- [ ] **Step 1:** Push and open the PR from `.github/pull_request_template.md`,
      body `Closes #5952` and `Refs #5948`.
- [ ] **Step 2:** Update the #5889 "Build-order timing" bullet to point at the
      PR. Edit the scratchpad copy of the body first, then
      `gh api -X PATCH repos/TEAMSchools/teamster/issues/5889 -F body=@<file>`
      and read the stored body back.

Checked and left alone: `scripts/audit_marts_yaml.py` does not assume `warn`. It
flags `warn` grain tests as `warn-masked`, which the rollout will clear. Its
fallback of `error` for an unset severity is wrong while the project default is
`warn`. It becomes right as folders flip, so it is not fixed here.
