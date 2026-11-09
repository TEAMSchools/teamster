# Warn Tests at Point of Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the source-data warn tests listed in #6146 to the earliest model
that sees the bad rows, and delete their downstream copies in the same PR.

**Architecture:** dbt test and YAML changes only, across 4 dbt projects
(powerschool, focus, finalsite, kipptaf). One commit per project; kipptaf gets
two (enrollment and contacts; assessments). No model SQL changes except comments
(item 12, item 13).

**Tech Stack:** dbt on BigQuery, dbt_utils, dagster-dbt checks.

**Spec:**
`docs/superpowers/specs/2026-10-26-warn-tests-point-of-entry-design.md`. Read it
first; this plan does not repeat its reasoning.

## Global Constraints

- Every new or moved test is `severity: warn`. Package tests set it explicitly;
  packages default to `error`.
- Every singular package test gets a `tests/properties.yml` entry with
  `meta.dagster.ref.name` (a model the test reads) and `package: <source>`.
  kipptaf entries omit `package:`.
- Every singular kipptaf test that reads more than 1 model gets
  `meta.dagster.ref`.
- Descriptions name the source system, what is wrong, and what to change there.
  No issue numbers in descriptions; `TODO(#N)` and `Refs` stay in SQL comments.
- Ticket columns: record, period, school. Network-level records (Illuminate
  assessment, repository field) return record id, title, academic year, and
  `creator_*` where available, no school.
- No row values in commits, PR text, or comments. Counts only.
- Run `uv run` for every dbt call. Use absolute worktree paths, never `cd` to
  the main checkout.
- `--target prod` is allowed only for `dbt compile` and `dbt parse` (they write
  nothing). Never `dbt build`/`run`/`test --target prod` or `--target staging`.

## How to check a test's count (used by every task)

dbt has no read-only way to run a test against prod, so compile it and run the
compiled SQL through the BigQuery MCP.

1. `uv run dbt deps --project-dir <wt>/src/dbt/<project>` once per project.
2. `uv run dbt compile --select <test_name> --project-dir <wt>/src/dbt/<project> --target prod 2>&1 | tail -n 5`
3. Read the compiled file under `<wt>/src/dbt/<project>/target/compiled/` and
   run `select count(*) from (<compiled sql>)` with
   `mcp__claude_ai_Google_Cloud_BigQuery__execute_sql_readonly` (project
   `teamster-332318`).
4. Compare with the expected count. A difference over about 10% gets explained
   (data moved since 2026-10-26 is a valid explanation) before you commit.

For a package test, compile in each consuming district: powerschool →
kippnewark, kippcamden, kipppaterson; focus → kippmiami; finalsite → all 4.

`<wt>` =
`/workspaces/teamster/.claude/worktrees/cbini/fix/claude-warn-tests-point-of-entry`.

## Review Focus

1. A package test in a district with no data for it (finalsite tests in
   kippmiami; powerschool tests in kipppaterson) should return 0 or real rows,
   not fail to compile. Task 3 counts kippmiami separately.
2. `int_powerschool__ps_enrollment_all.yearid` is null when `entrydate` falls
   outside every term. The skipped-grade test derives the year from `entrydate`,
   so those stints are not dropped. Task 1 checks that the null-yearid count is
   unchanged by the derivation.
3. `academic_year_clean` of 0 or 1 makes `date()` throw. The item 9 test filters
   `academic_year_clean >= 2000` before calling `date()`. Task 5 compiles and
   runs it over all history to prove no error.
4. A singular package test without `package:` silently never becomes a Dagster
   check. Task 6 checks every new entry in the parsed manifest.
5. Repositories with no `int_illuminate__repositories` row must not fail item
   10's test. An inner join excludes them; Task 5 checks the count is 6, not 14.

---

### Task 1: powerschool package (items 1 NJ, 11, 12)

**Files:**

- Delete:
  `src/dbt/powerschool/tests/base_powerschool__student_enrollments__cohort_not_ahead_of_entry.sql`
- Create:
  `src/dbt/powerschool/tests/int_powerschool__ps_enrollment_all__no_skipped_grade.sql`
- Create:
  `src/dbt/powerschool/tests/int_powerschool__spenrollments__no_concurrent_bucket_per_subject.sql`
- Modify: `src/dbt/powerschool/tests/properties.yml` (remove the
  `cohort_not_ahead_of_entry` entry at about line 125; add 2 entries)
- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__ps_enrollment_all.yml:3-13`

**Interfaces:**

- Produces: test names `int_powerschool__ps_enrollment_all__no_skipped_grade`
  and `int_powerschool__spenrollments__no_concurrent_bucket_per_subject`, and
  the named test `int_powerschool__ps_enrollment_all__unique_student_entrydate`.
  Task 4 names the last one in a SQL comment.

- [ ] **Step 1: Write
      `int_powerschool__ps_enrollment_all__no_skipped_grade.sql`**

  Logic: from `ref("int_powerschool__ps_enrollment_all")`, exclude
  `schoolid = 999999` and grades outside 0–12. Derive `academic_year` from
  `entrydate` (July starts the year: `extract(year from entrydate)` minus 1 when
  the month is before 7). Take 1 row per `studentid, academic_year` with the
  highest `grade_level` and that row's `schoolid` (rank by `grade_level desc`,
  `entrydate desc`). In a second CTE, compute `lag(academic_year)` and
  `lag(grade_level)` over `partition by studentid order by academic_year`.
  Return rows where `academic_year - prior_academic_year = 1`,
  `grade_level - prior_grade_level > 1`, and `grade_level between 9 and 12`.
  Output columns: `studentid`, `student_number`, `academic_year`, `schoolid`,
  `prior_grade_level`, `grade_level`. Follow `.claude/rules/dbt-sql.md`: ranked
  column plus `where`, no `qualify`.

- [ ] **Step 2: Check its count**

  Use _How to check a test's count_. Expected: Newark plus Camden total 117,
  Paterson 0. Current-year rows: 7.

- [ ] **Step 3: Write
      `int_powerschool__spenrollments__no_concurrent_bucket_per_subject.sql`**

  From `ref("int_powerschool__spenrollments")` where
  `specprog_name like 'Bucket%'`, derive `subject` as the text after the hyphen
  (trimmed). Self-join on `studentid`, `academic_year`, `subject`, with
  `a.specprog_name < b.specprog_name` and overlapping ranges
  (`a.enter_date < b.exit_date and b.enter_date < a.exit_date`, treating a null
  exit as open). Return `studentid`, `academic_year`, `subject`, both program
  names, both enter dates. For the school, join whatever upstream model holds
  the student's `schoolid`. Read `int_powerschool__spenrollments.sql` first; if
  `stg_powerschool__spenrollments` carries `schoolid`, join that on `dcid`.

- [ ] **Step 4: Check its count**

  Expected: 54 pairs, all AY2025 (Camden 29, Newark 20, Paterson 5). If the
  overlap condition drops any pair, check the 1 inverted-date Newark record
  #5693 mentions (exit before enter). Treat an inverted range as overlapping
  when the enter dates match.

- [ ] **Step 5: Edit `tests/properties.yml`**

  Remove the `cohort_not_ahead_of_entry` entry. Add both new entries with
  `config: severity: warn` and `meta.dagster.ref`
  (`int_powerschool__ps_enrollment_all` / `int_powerschool__spenrollments`,
  `package: powerschool`). Descriptions:

  - Skipped grade: a high school student's grade rose by more than 1 between
    consecutive years. Fix the grade or the missing enrollment year in
    PowerSchool. Summer credit recovery can legitimately produce this shape.
  - Bucket: 2 Bucket programs for 1 subject are active at the same time. The
    lower-numbered bucket is correct; delete the other special-program record in
    PowerSchool. Back-to-back buckets are normal amendments and are not flagged.

- [ ] **Step 6: Name and describe the item 12 test**

  In `int_powerschool__ps_enrollment_all.yml`, add
  `name: int_powerschool__ps_enrollment_all__unique_student_entrydate` and a
  `description:` to the existing `dbt_utils.unique_combination_of_columns`. The
  description: 2 stints for 1 student start on the same day; correct the
  duplicate enrollment record in PowerSchool. Keep the `where` and its comment.

- [ ] **Step 7: Parse**

  Run:
  `uv run dbt parse --no-partial-parse --project-dir <wt>/src/dbt/kippnewark 2>&1 | tail -n 5`
  Expected: no errors.

- [ ] **Step 8: Commit**

  `git -C <wt> add` the 2 new files, then
  `git -C <wt> add -u src/dbt/powerschool`. Message:
  `fix(powerschool): move skipped-grade, bucket and entry-date checks to the point of entry`
  with `Refs #6146`.

### Task 2: focus package (items 1 Miami, 2a, 3 Miami, 4)

**Files:**

- Create:
  `src/dbt/focus/tests/int_focus__student_enrollment_roster__no_skipped_grade.sql`
- Create: `src/dbt/focus/tests/int_focus__calendar_day__has_enrollment.sql`
- Modify: `src/dbt/focus/tests/properties.yml` (add 2 entries)
- Modify:
  `src/dbt/focus/models/staging/properties/stg_focus__course_periods.yml`
  (`teacher_id`)
- Modify:
  `src/dbt/focus/models/intermediate/properties/int_focus__student_contacts.yml:83,88`

**Interfaces:**

- Consumes: the skipped-grade logic from Task 1, Step 1.
- Produces: test names above. Task 4 deletes the kipptaf tests these replace.

- [ ] **Step 1: Write the Miami skipped-grade test**

  Same logic as Task 1 Step 1, on `ref("int_focus__student_enrollment_roster")`.
  That model already has `academic_year` and `schoolid`, so no year derivation.
  Return `student_number`, `academic_year`, `schoolid`, `prior_grade_level`,
  `grade_level`.

- [ ] **Step 2: Check its count**

  Expected: unmeasured; record it in the commit message. Current year should be
  0, matching today's Miami cohort test.

- [ ] **Step 3: Write `int_focus__calendar_day__has_enrollment.sql`**

  First confirm that `int_focus__calendar_day.schoolid` and
  `int_focus__student_enrollment_roster.schoolid` hold the same id kind: query a
  few distinct values of each with BigQuery MCP. Then left-join the calendar to
  the distinct `schoolid, academic_year` pairs of the roster. Return `schoolid`,
  `academic_year`, `count(*) as n_days` where the roster side is null, grouped
  by `schoolid, academic_year`.

- [ ] **Step 4: Check its count**

  Expected: 2 schools, 212 days each.

- [ ] **Step 5: Add the generic tests**

  - `stg_focus__course_periods.yml`, column `teacher_id`: `not_null` with
    `config: severity: warn`. Description on the column test: the course period
    has no lead teacher in Focus; assign one on the course period. Move the
    column to the top of `columns:`. Expected: 97 rows (all years).
  - `int_focus__student_contacts.yml`: `not_null` with `severity: warn` on
    `contact_first_name` and `contact_last_name`. Expected: first 2, last 2.
    Move both columns to the top of `columns:`.

- [ ] **Step 6: Add the 2 singular entries to `tests/properties.yml`**

  `severity: warn`, `meta.dagster.ref` to `int_focus__student_enrollment_roster`
  / `int_focus__calendar_day`, `package: focus`. Calendar description: a Focus
  school has a calendar for the year but no enrolled students; remove the
  calendar or enroll the students in Focus.

- [ ] **Step 7: Parse and commit**

  `uv run dbt parse --no-partial-parse --project-dir <wt>/src/dbt/kippmiami 2>&1 | tail -n 5`,
  then commit as in Task 1:
  `fix(focus): add point-of-entry checks for grade history, lead teacher, contact names and empty calendars`.

### Task 3: finalsite package (items 3 NJ, 8)

**Files:**

- Modify:
  `src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_contacts.yml:85,94`
- Modify:
  `src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__contact_id_attributes.yml`

**Interfaces:**

- Produces: generic tests that Task 4 relies on when it deletes the kipptaf
  copies.

- [ ] **Step 1: Add `not_null` with `severity: warn` on both name columns**

  Description: the Finalsite contact has no first or last name; add it on the
  contact in Finalsite. Move both columns to the top of `columns:`.

- [ ] **Step 2: Check its count per district**

  Expected: last name, Newark 4 and Camden 6. Count kippmiami and kipppaterson
  separately. If kippmiami has failures, decide whether they are real Finalsite
  defects (keep them) or rows Miami does not use. If they are unused, add
  `where:` to scope them out, and say why in a YAML comment.

- [ ] **Step 3: Add the item 8 test**

  On column `focus_student_id_prefixed`: `unique` with
  `config: where: focus_student_id_prefixed is not null, severity: warn`.
  Description: more than 1 Finalsite record carries the same Focus student id;
  merge or correct the duplicate in Finalsite. Expected: 6 keys, all kippmiami.

- [ ] **Step 4: Parse and commit**

  Parse kippnewark and kippmiami. Commit:
  `fix(finalsite): check contact names and Focus id uniqueness at the package model`.

### Task 4: kipptaf enrollment, contacts and Focus (items 1, 2b, 3, 4, 8, 12)

**Files:**

- Delete:
  `src/dbt/kipptaf/tests/int_extracts__student_enrollments__miami_cohort_not_ahead_of_entry.sql`
- Delete:
  `src/dbt/kipptaf/tests/int_students__calendar_day__zero_enrollment_in_session_days.sql`
- Modify:
  `src/dbt/kipptaf/tests/test_focus_course_sections_teacher_resolves.sql`
- Modify: `src/dbt/kipptaf/tests/properties.yml` (remove 2 entries at about
  lines 801 and 983; edit the entry at about 516)
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__contacts.yml:64-90`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__course_sections.yml:45`
- Modify:
  `src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__contact_id_attributes.yml:8-17,35-48`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_student_attendance_streaks.sql:14-22`

**Interfaces:**

- Consumes: Task 1's
  `int_powerschool__ps_enrollment_all__unique_student_entrydate`; Tasks 2–3 test
  names (for description cross-references).

- [ ] **Step 1: Rewrite the teacher-resolves test (item 2b)**

  Keep the current filter (`kippmiami`, `teachernumber is null`, years from the
  first Focus year). Inner join `ref("int_focus__course_periods")` on
  `cs.sections_dcid = cp.course_period_id`, plus `_dbt_source_project`. Keep
  only `cp.teacher_id is not null`. Return `sections_dcid`, `sections_schoolid`,
  `cp.period_id`, `cp.teacher_id`, `terms_academic_year`, `_dbt_source_project`.
  Expected: 37 rows. Update its description to say that a null lead teacher is
  now caught by the focus package test on
  `stg_focus__course_periods.teacher_id`, and that this test covers a Focus
  teacher with no ADP staff-roster match. Update the mention at
  `int_students__course_sections.yml:45` to match.

- [ ] **Step 2: Delete the 2 moved singular tests and their entries**

- [ ] **Step 3: Remove the 2 `not_null` tests on `int_students__contacts`**

  Rewrite the comment at lines 64–67 to point to the package tests
  (`int_focus__student_contacts`, `int_finalsite__student_contacts`).

- [ ] **Step 4: Remove the kipptaf item 8 test**

  Delete the model-level `unique_combination_of_columns` (lines 8–17). Rewrite
  the `focus_student_id_prefixed` description sentence: uniqueness is tested on
  the finalsite package model, which `rpt_tableau__fresh_dashboard_qc` relies
  on. Keep the YAML valid if `data_tests:` becomes empty: remove the key. Then
  check whether the model still has a uniqueness test. The per-layer rule
  exempts kipptaf union views.

- [ ] **Step 5: Replace the `TODO(#4835)` block (item 12)**

  In `fct_student_attendance_streaks.sql`, replace lines 14–22 with 1 comment
  line: the dedupe picks the longest stint when 2 share an entry date;
  `int_powerschool__ps_enrollment_all__unique_student_entrydate` flags them at
  the source. The SQL logic must not change.

- [ ] **Step 6: Check counts, parse and commit**

  Compile and count the rewritten teacher test (37). Run
  `uv run dbt parse --no-partial-parse --project-dir <wt>/src/dbt/kipptaf 2>&1 | tail -n 5`.
  Commit: `fix(dbt): drop kipptaf copies of checks moved to source packages`.

### Task 5: kipptaf assessments (items 5, 7, 9, 10, 13)

**Files:**

- Create:
  `src/dbt/kipptaf/tests/stg_illuminate__dna_assessments__students_assessments__taken_before_academic_year.sql`
- Create:
  `src/dbt/kipptaf/tests/stg_illuminate__dna_repositories__repository_fields__sight_words_unique_label.sql`
- Modify: `src/dbt/kipptaf/tests/properties.yml` (2 new entries; edit the
  `int_assessments__scaffold__replacement_region_untagged` entry at about
  line 323)
- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__academic_goals.yml:9-16`
- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__scaffold.yml:55-68`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__sight_words_dashboard.yml:4-27`
- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__response_rollup.sql:108-115,166-168`
- Modify:
  `src/dbt/kipptaf/models/illuminate/dlt/intermediate/properties/int_illuminate__assessments.yml:9-13`
- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__kippfwd_miami_roster.sql:116`

**Interfaces:**

- Consumes: nothing from earlier tasks.

- [ ] **Step 1: Write the item 9 test**

  `stg_illuminate__dna_assessments__students_assessments` (`sa`) inner join
  `int_illuminate__assessments` (`a`) on `assessment_id`. A CTE filters
  `a.academic_year_clean >= 2000` (comment: Illuminate holds 0 and 1 as junk
  years) and derives
  `academic_year_start_date = date(academic_year_clean, 7, 1)`. The final select
  keeps `date_taken < academic_year_start_date`. Return
  `sa.student_assessment_id`, `sa.assessment_id`, `a.title`,
  `a.academic_year_clean`, `sa.date_taken`, and the `creator_*` columns
  `int_illuminate__assessments` has (check its YAML).

- [ ] **Step 2: Check its count**

  Expected: 18,391 rows across 429 assessments; 2,237 rows across 18 assessments
  in the current year. No `date()` error.

- [ ] **Step 3: Write the item 10 test**

  Group `stg_illuminate__dna_repositories__repository_fields` by
  `repository_id, label` having `count(*) > 1`. Inner join
  `int_illuminate__repositories` on `repository_id` where
  `scope = 'Sight Words Quiz'`. Return `repository_id`, the repository title,
  `label`, and the count. Check the exact column names in both YAML files.

- [ ] **Step 4: Check its count**

  Expected: 6 repositories. 14 means the scope filter or the inner join is wrong
  (Review Focus 5).

- [ ] **Step 5: Decide the dashboard grain test (item 10)**

  Count failures of the `unique_combination_of_columns` on
  `rpt_tableau__sight_words_dashboard` (repository_id, student_number,
  sight_word) against prod. If 0: set it to `severity: error`, drop the
  `TODO(#5700)`. If more than 0: keep `warn`, replace the TODO with
  `TODO(#6146): fails until the Illuminate repositories flagged by the repository_fields sight-words test are fixed`.
  Either way, update the description's repeat-row sentence (lines 4–7) to name
  the source test.

- [ ] **Step 6: Add properties entries**

  Item 9: `meta.dagster.ref` to
  `stg_illuminate__dna_assessments__students_assessments`. Description: the
  student took the assessment before its academic year began; correct the
  assessment's academic year (or the date taken) in Illuminate. Item 10: ref
  `stg_illuminate__dna_repositories__repository_fields`. Description: a Sight
  Words repository holds the same field label more than once (often the
  placeholder `TBD`); rename or remove the duplicate field in Illuminate. Item
  7: add `meta.dagster.ref: {name: int_assessments__scaffold}` to the existing
  entry and rewrite its description per the spec (AppSheet `regions_assessed`
  tag, or remove the student in Illuminate).

- [ ] **Step 7: Delete items 5 and 9's downstream tests**

  Delete the `unique_combination_of_columns` in
  `int_assessments__academic_goals.yml`. Check that the model keeps a uniqueness
  test; if this was its only one, keep it instead and note it in the commit.
  Delete the `expression_is_true` in `int_assessments__scaffold.yml:55-68`.

- [ ] **Step 8: Rewrite the item 13 comments**

  `int_assessments__response_rollup.sql` lines 108–115: the partition can hold
  rows at more than 1 school when a student is rostered to the canonical
  assessment at a second school; the ordering credits the result to the school
  of the sitting. Remove "Once #3801 is resolved...". Lines 166–168: remove the
  "See #3801." sentence. Leave line 70 alone. In
  `int_illuminate__assessments.yml` lines 9–13, remove the "cross-school groups
  in response_rollup" claim. In `rpt_gsheets__kippfwd_miami_roster.sql:116`,
  drop `#4795` and keep `#4796`.

- [ ] **Step 9: Prove the SQL edits are comment-only**

  For both `.sql` files, strip `--` and `/* */` comments from
  `git show HEAD:<path>` and the working copy, collapse whitespace, and diff.
  Expected: identical.

- [ ] **Step 10: Parse and commit**

  kipptaf parse with `--no-partial-parse`. Commit:
  `fix(dbt): move Illuminate assessment checks to their point of entry`.

### Task 6: Whole-branch verification and PR

**Files:** none changed unless a check fails.

- [ ] **Step 1: Diff test nodes against main**

  For kipptaf, kippnewark and kippmiami: parse main (a temporary worktree from
  `origin/main` under `/workspaces/teamster/.claude/worktrees/`, removed after)
  and the branch with `--no-partial-parse`. Extract `resource_type == 'test'`
  node names from each `target/manifest.json` with `jq` and diff. Expected:
  exactly the adds, removes and renames in Tasks 1–5.

- [ ] **Step 2: Check Dagster refs**

  In each branch manifest, every new singular test's `config.meta.dagster.ref`
  names a model in its `depends_on.nodes`. Every package test also has `package`
  set. (Review Focus 4.)

- [ ] **Step 3: Sweep for stale names**

  `rg -n --glob '*.{sql,yml,md}' '<each deleted test name>' <wt>/src <wt>/docs <wt>/.claude`
  Expected: no hits outside this plan and the spec.

- [ ] **Step 4: Lint**

  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <every changed file> </dev/null`
  from inside `<wt>`. Fix lint findings; formatting is the hook's.

- [ ] **Step 5: Push and open the PR**

  Body from `.github/pull_request_template.md`, `Refs #6146` (not `Closes`; item
  6 is held). List each item with its old and new location and its count. End
  with the attribution line. Then update #6146 per the spec's last _Left to the
  builder_ bullet, and follow `CLAUDE.local.md` for CI and review.
