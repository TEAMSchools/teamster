# SGP dashboard, PR 2 (kipptaf models) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the 3 report models and the exposure behind the SGP dashboard:
one row per SGP score for the Schools tab, one row per score and matched teacher
for the Teachers tab, and a username-to-school access table.

**Architecture:** `int_assessments__state_nj_scores` gains the state file's
economic disadvantage status from PR 1 and a derived boolean; multilingual
learners come from its existing `aligned_ml_status`. 3 new
`rpt_tableau__sgp_dashboard_*` views read it (the A2 exception tracked in #6480)
plus the enrollment, section, staff, location, and calendar marts. The
teacher-matching rules (70% student, 60% teacher, in-session school days) live
inside the teachers model as a CTE chain with unit tests.

**Tech Stack:** dbt (BigQuery), `dbt_utils`, dbt unit tests, kipptaf key macros
(`student_key`).

**Spec:** `docs/superpowers/specs/2026-11-24-sgp-dashboard-design.md` (_Pull
request 2_, _Tests_, _What the data holds_, _Appendix_).

## Global Constraints

- Start only after PR 1 merges and Dagster rebuilds
  `int_cambium__all_assessments` in Newark, Camden, and Paterson. Task 0 checks.
- New branch from `origin/main`, created per the root CLAUDE.md _Branches_ flow
  (ask worktree or branch switch first). Worktree root below is `W2` =
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-sgp-dashboard-models`
  (branch `anthonygwalters/feat/claude-sgp-dashboard-models`); every path and
  `--project-dir` is absolute under `W2`, every git call is `git -C W2`. No
  issue link; PR body says `Refs #6279` and links #6480 for the A2 exception.
- Model names exactly `rpt_tableau__sgp_dashboard_schools`,
  `rpt_tableau__sgp_dashboard_teachers`, `rpt_tableau__sgp_dashboard_access`;
  SQL in `W2/src/dbt/kipptaf/models/extracts/tableau/`, YAML in
  `.../extracts/tableau/properties/`. Exposure name `sgp_dashboard`.
- Never hardcode a school year. Rows are every score with
  `student_growth_percentile is not null`.
- Growth level: `Low` below 35, `Typical` 35 to 65, `High` above 65.
- Matching: roles `Lead Teacher` and `Co-teacher` only; student share at least
  `0.70`, teacher share at least `0.60`; in-session days from
  `dim_school_calendars` at the student's school on test day, from the start of
  that academic year (`dim_dates.academic_year`) through the day before the
  test. Section `exit_date` is exclusive; teacher `effective_end_date` is
  inclusive (checked: the next lead starts the day after); a null
  `effective_end_date` is open-ended. Lead wins over Co-teacher. "Lead in both
  subjects" needs at least 10 lead students in each subject at the school.
- Race label: `aligned_aggregate_ethnicity`, with `Other` relabeled
  `Two or more races`.
- Multilingual learner: `is_multilingual_learner` = `aligned_ml_status = 'ML'`,
  the state file's `multilingual_learner` flag, the same rule STAT uses
  (requester's decision, 2026-11-24). `nj_ml_status` is not used.
- Economic disadvantage: `is_economically_disadvantaged`, null where the state
  file has no status (all of Paterson); the workbook shows null as
  `Not reported`. Never filled from PowerSchool (requester's decision).
- No `student_number` or student names in any report model. Tag student-level
  content columns `contains_pii: true` per `.claude/rules/ferpa-pii.md` tiers 1
  to 3; teacher names too (staff policy).
- Report-model tests set `config: severity: error`. Unit-test inputs that mock
  `int_assessments__state_nj_scores` use `format: sql` (columns added in this
  PR; dict fixtures fail introspection in CI). So does any input that mocks
  `int_cambium__all_assessments` with `economic_disadvantage_status`: CI's
  `zz_stg_kipptaf_cambium` copy is a `select *` view over prod whose stored
  schema predates the column.
- Every dbt command is `uv run dbt ...`. `<dev flags>` in the steps means
  `--target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod`.
  No `--target staging` write without the user's go-ahead in the turn before.
- No PII values in commits, the PR body, or comments: aggregates only, and no
  staff names.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`;
  the PR body ends with
  `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

## Review Focus

1. A score with no enrollment stint on its test date would drop silently from an
   inner join. Both score-carrying models left-join and carry an `error`
   `not_null` on `location_key`; Task 5 confirms 0 nulls.
2. A test date equal to one stint's `exit_date` and the next stint's
   `entry_date` must match only the second stint (half-open). Task 2 has a unit
   test for it.
3. A window of 0 in-session days (missing calendar, test on the first day) makes
   every share undefined. `safe_divide` gives null, the row fails both rules,
   and Task 5 reports how many scores have `window_day_count` 0 or null
   (expected 0).
4. A school with no access row is invisible on the Teachers tab to everyone but
   KTAF. Task 5 lists every ES and MS `location_key` in the schools model with
   no access row (expected none; TEAM is covered by its head of school because
   its school leader is also a head of schools and `dim_locations` leaves TEAM's
   school leader blank).
5. A person who is both a school leader and a head of school must get one access
   row per school, not two. Task 4 has a unit test for it.

---

### Task 0: confirm PR 1 reached kipptaf

**Files:** none.

- [ ] **Step 1:** With the BigQuery MCP, check that `INFORMATION_SCHEMA.COLUMNS`
      lists `economic_disadvantage_status` on
      `<d>_cambium.int_cambium__all_assessments` for each of `kippnewark`,
      `kippcamden`, `kipppaterson`, and on
      `kipptaf_cambium.int_cambium__all_assessments`. Expected: present in all 4
      (confirmed 2026-11-24).
- [ ] **Step 2:** Confirm
      `select countif(economic_disadvantage_status is not null) from zz_stg_kipptaf_cambium.int_cambium__all_assessments`
      runs and returns more than 0. That copy is a `select *` view over prod, so
      it returns the column although its stored schema lacks it; no staging
      write is needed (confirmed 2026-11-24: 12,347 of 13,211 rows).

### Task 1: state-file student groups in `int_assessments__state_nj_scores`

**Files:**

- Modify:
  `W2/src/dbt/kipptaf/models/assessments/intermediate/int_assessments__state_nj_scores.sql`
- Modify:
  `W2/src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__state_nj_scores.yml`
  (2 column entries; add a sibling unit test)

**Interfaces:**

- Consumes: `int_cambium__all_assessments.economic_disadvantage_status` (PR 1).
- Produces on `int_assessments__state_nj_scores`: `economic_disadvantage_status`
  (STRING) and `is_economically_disadvantaged` (BOOL), both null on Pearson
  rows. Tasks 2 and 3 read `is_economically_disadvantaged`, and
  `aligned_ml_status` as it is today.

- [ ] **Step 1: Write the failing unit test**
      `test_int_assessments__state_nj_scores_economic_status`. Mock
      `int_cambium__all_assessments` with `format: sql` (Global Constraints).
      Cambium given rows and expected outputs:

  | `economic_disadvantage_status` | `is_economically_disadvantaged` |
  | ------------------------------ | ------------------------------- |
  | `Y`                            | `true`                          |
  | `N`                            | `false`                         |
  | null                           | null                            |
  | `X`                            | null                            |

  plus 1 Pearson row expecting null in both columns. The `X` row is an unknown
  code: it proves the derivation is the defense for the staging `warn` test
  (added 2026-11-24 from the PR #6483 review).

- [ ] **Step 2: Run it and watch it fail.**
      `uv run dbt test --select test_int_assessments__state_nj_scores_economic_status --project-dir W2/src/dbt/kipptaf <dev flags> 2>&1 | tail -n 30`.
      Expected: FAIL, the output lacks the columns.

- [ ] **Step 3: Implement.** Pearson branch: `cast(null as string)` for
      `economic_disadvantage_status` and `cast(null as bool)` for
      `is_economically_disadvantaged`, as the branch's last columns (S17
      positional order). Cambium branch, same positions: the raw column, then a
      `case` mapping `Y` to `true`, `N` to `false`, else null (S15: 2
      conditions). Final select: pass both through after
      `u.student_growth_percentile`. yml entries with descriptions (null means
      the state file has no status, as for every Paterson row) and
      `contains_pii: true`.

- [ ] **Step 4: Run the unit tests and the model build.**
      `uv run dbt build --select int_assessments__state_nj_scores --project-dir W2/src/dbt/kipptaf <dev flags> 2>&1 | tail -n 30`.
      Expected: PASS, both unit tests and every data test (the known
      `test_incorrect_student_number_pearson` warn may remain).

- [ ] **Step 5: Reconcile** against prod with the BigQuery MCP: same row count;
      for `academic_year = 2025`, `countif(is_economically_disadvantaged)`
      equals the count of `economic_disadvantage_status = 'Y'`, and STAT's
      `aligned_ml_status` values are unchanged row for row (`count(*)` where dev
      and prod differ on `student_test_uuid` join = 0).

- [ ] **Step 6: Commit**
      `feat(dbt): carry state-file economic status into NJ state scores` with
      `Refs #6279`.

### Task 2: `rpt_tableau__sgp_dashboard_schools`

**Files:**

- Create:
  `W2/src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__sgp_dashboard_schools.sql`
- Create:
  `W2/src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__sgp_dashboard_schools.yml`

**Interfaces:**

- Consumes: Task 1's columns; `dim_student_enrollments`, `dim_locations`,
  `dim_regions`.
- Produces (one row per SGP score; grain `student_test_uuid`):
  `student_test_uuid`, `student_key`, `academic_year`, `test_date`, `region`
  (`dim_regions.name`), `location_key`, `school` (`dim_locations.abbreviation`),
  `school_name` (`dim_locations.name`), `grade_band`, `grade_level_tested`
  (`grade_level_when_assessed`), `subject` (`discipline`), `test_code`,
  `student_growth_percentile`, `growth_level`, `is_proficient`,
  `race_ethnicity_group`, `disability_status` (`aligned_iep_status`),
  `is_multilingual_learner` (`aligned_ml_status = 'ML'`),
  `is_economically_disadvantaged` (nullable). Task 3 repeats the score-to-school
  join with the same rule; Task 5 reconciles both.

- [ ] **Step 1: Write the failing unit test**
      `test_rpt_tableau__sgp_dashboard_schools_rules`. Given 6 scores (one
      student-subject each) with SGP 34, 35, 65, 66, null, and 50; expect 5 rows
      (the null SGP drops) with `growth_level` `Low`, `Typical`, `Typical`,
      `High`, `Typical`. The SGP 50 student has 2 enrollment stints, the first
      ending (`exit_date_key`) on the test date and the second starting on it;
      expect the second stint's `school`. One student has
      `aligned_aggregate_ethnicity = 'Other'`; expect `Two or more races`. One
      has `aligned_ml_status = 'ML'` and a null `is_economically_disadvantaged`;
      expect `is_multilingual_learner` true and `is_economically_disadvantaged`
      null.

- [ ] **Step 2: Run it and watch it fail** (model does not exist).

- [ ] **Step 3: Implement.** A CTE computes
      `{{ student_key("student_number") }} as student_key` from the scores where
      `student_growth_percentile is not null`; left join
      `dim_student_enrollments` on `student_key`, `academic_year`,
      `entry_date_key <= test_date`, `exit_date_key > test_date` (S13); left
      join `dim_locations` and `dim_regions`. Final select enumerates the
      Interfaces columns (A9). yml: `contract` comes from the folder default;
      model `description`; every column described; `unique` on
      `student_test_uuid` and `not_null` on `location_key`, both
      `config: {severity: error}`; `contains_pii: true` on every student-level
      content column (SGP, growth level, proficiency, grade, all 4 groups,
      `test_date`).

- [ ] **Step 4: Build and watch it pass.**
      `uv run dbt build --select rpt_tableau__sgp_dashboard_schools --project-dir W2/src/dbt/kipptaf <dev flags> 2>&1 | tail -n 30`.
      Expected: PASS, unit test and both data tests.

- [ ] **Step 5: Commit** `feat(dbt): add the SGP dashboard schools model` with
      `Refs #6279`.

### Task 3: `rpt_tableau__sgp_dashboard_teachers`

**Files:**

- Create:
  `W2/src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__sgp_dashboard_teachers.sql`
- Create:
  `W2/src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__sgp_dashboard_teachers.yml`

**Interfaces:**

- Consumes: as Task 2, plus `dim_student_section_enrollments`,
  `dim_course_sections`, `dim_courses`, `bridge_course_section_teachers`,
  `dim_staff`, `dim_school_calendars`, `dim_dates`.
- Produces (grain `student_test_uuid` + `staff_key`): every Task 2 column except
  `school_name`, plus `staff_key`, `teacher_name` (`dim_staff.full_name`),
  `teacher_role` (`Lead Teacher` or `Co-teacher`), `window_day_count`,
  `student_day_count`, `student_share`, `teacher_share` (the highest share among
  that teacher's sections for the student), `teacher_shared_student_count`,
  `teacher_other_teacher_count`, `is_lead_in_both_subjects`. Task 5 and the
  workbook plan read these names.

- [ ] **Step 1: Write the failing unit tests**, one per case, each with its own
      small calendar of 10 in-session days before the test (so 7 days is 70%, 6
      is 60%):

  - `..._student_at_70_percent`: student in the section 7 of 10 days, teacher
    all 10. Expect 1 row, `student_share` 0.7.
  - `..._student_below_70_percent`: 6 of 10. Expect 0 rows.
  - `..._teacher_at_60_percent`: teacher assigned 6 of 10 days, ending on day 6
    (inclusive end). Expect 1 row, `teacher_share` 0.6.
  - `..._teacher_below_60_percent`: 5 of 10. Expect 0 rows for that teacher.
  - `..._same_teacher_two_sections`: student 5 days in section A then 5 in
    section B, same lead in both. Expect 1 row, `student_day_count` 10.
  - `..._two_teachers_split`: same move, different leads. Expect 0 rows.
  - `..._co_teacher_and_gradebook`: one section with a lead, a co-teacher, and a
    `Gradebook Access (edit)` assignment. Expect 2 rows (lead, co-teacher).
  - `..._lead_wins`: one person lead on section A and co-teacher on section B
    for the same student. Expect 1 row, `teacher_role` `Lead Teacher`.
  - `..._dropped_and_readded`: 2 enrollments in one section, days 1–4 and 4–10
    (overlap on day 4). Expect `student_day_count` 10, not 11.
  - `..._open_ended_teacher`: `effective_end_date` null. Expect the teacher to
    pass.
  - `..._context_columns`: 2 teachers sharing 3 students; expect
    `teacher_shared_student_count` 3 and `teacher_other_teacher_count` 1 on
    each. A lead with 10 ELA and 10 math students at one school: expect
    `is_lead_in_both_subjects` true; with 9 math students: false.

- [ ] **Step 2: Run them and watch them fail** (model does not exist).

- [ ] **Step 3: Implement** as a CTE chain:

  1. `scores`: Task 2's score-to-school rule (left join, same keys).
  2. `window_days`: one row per score and in-session date:
     `dim_school_calendars` at the score's `location_key` with `is_in_session`,
     joined to `dim_dates` on `date_key` with `academic_year` equal to the
     score's, and `date_key < test_date`.
  3. `sections`: the student's sections in the subject:
     `dim_student_section_enrollments` (not `is_homeroom`; keep dropped
     sections) joined through `student_enrollment_key` to
     `dim_student_enrollments.student_key` and through `course_section_key` to
     `dim_course_sections` and `dim_courses` with `academic_subject` equal to
     the score's `subject`.
  4. `assignments`: `bridge_course_section_teachers` for those sections, roles
     `Lead Teacher` and `Co-teacher`, with
     `coalesce(effective_end_date, '9999-12-31')` as an inclusive end.
  5. `teacher_section_share`: per score, section, and teacher, count of window
     dates inside the assignment, divided by `window_day_count`; keep at least
     0.60.
  6. `student_teacher_days`: per score and teacher, `count(distinct date_key)`
     of window dates on which the student is in any kept section of that teacher
     (`entry_date <= date_key < exit_date`); keep `student_share` at least 0.70.
     Role: `Lead Teacher` if any kept section has the person as lead, else
     `Co-teacher`.
  7. `teacher_context`: per `staff_key`, `location_key`, and `subject`, the
     shared-student and other-teacher counts from a self-join on
     `student_test_uuid`; per `staff_key` and `location_key`, the lead counts by
     subject for `is_lead_in_both_subjects`.

  Use `safe_divide` for every share. Comment each threshold literal (S20). yml:
  `dbt_utils.unique_combination_of_columns` on `student_test_uuid`, `staff_key`
  and `not_null` on `location_key`, both `severity: error`; descriptions say the
  rule each column implements; `contains_pii: true` as in Task 2, plus
  `teacher_name`.

- [ ] **Step 4: Build and watch it pass.**
      `uv run dbt build --select rpt_tableau__sgp_dashboard_teachers --project-dir W2/src/dbt/kipptaf <dev flags> 2>&1 | tail -n 30`.
      Expected: PASS, all unit and data tests.

- [ ] **Step 5: Commit** `feat(dbt): add the SGP dashboard teachers model` with
      `Refs #6279`.

### Task 4: `rpt_tableau__sgp_dashboard_access`

**Files:**

- Create:
  `W2/src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__sgp_dashboard_access.sql`
- Create:
  `W2/src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__sgp_dashboard_access.yml`

**Interfaces:**

- Consumes: `dim_locations`, `dim_staff`.
- Produces (grain `tableau_username` + `location_key`): `tableau_username`
  (`dim_staff.active_directory_username`), `location_key`,
  `is_school_leader_access`, `is_head_of_school_access`. The workbook joins the
  teachers model to it on `location_key` and filters on `USERNAME()`.

- [ ] **Step 1: Write the failing unit test**
      `test_rpt_tableau__sgp_dashboard_access_paths`: region R has schools A and
      B, with school leader S on A and head of school H on both; region Q has
      school C with leader T. A person P is school leader of B and head of
      school of B. A staff row with a null username leads school C2. Expect: S
      on A; H on A and B; T on C; P on A and B (once each, both flags true on
      B); nothing for the null username.

- [ ] **Step 2: Run it and watch it fail.**

- [ ] **Step 3: Implement.** Union the school-leader path (each location's
      `school_leader_staff_key`) and the head-of-school path (every location in
      any region where the person is a location's `head_of_school_staff_key`),
      drop null usernames, then group by `tableau_username` and `location_key`
      with `logical_or` for the 2 flags. yml: the unique combination and
      `not_null` on both grain columns, `severity: error`; `contains_pii: true`
      on `tableau_username`.

- [ ] **Step 4: Build and watch it pass.** Same command shape as Task 3.

- [ ] **Step 5: Commit** `feat(dbt): add the SGP dashboard access model` with
      `Refs #6279`.

### Task 5: exposure, verification, and PR 2

**Files:**

- Modify: `W2/src/dbt/kipptaf/models/exposures/tableau.yml` (new `sgp_dashboard`
  entry: `label: SGP Dashboard`, `type: dashboard`, `owner.name: Data Team`,
  `depends_on` the 3 models, `config.meta.dagster.kinds: [tableau]`; no
  `asset.metadata.id` yet)

- [ ] **Step 1: Add the exposure** and run
      `uv run dbt parse --project-dir W2/src/dbt/kipptaf 2>&1 | tail -n 5`.
      Expected: no errors.

- [ ] **Step 2: Run the suite.**
      `uv run dbt build --select int_assessments__state_nj_scores+ --project-dir W2/src/dbt/kipptaf <dev flags> 2>&1 | tail -n 40`.
      Expected: PASS for the 4 changed or new models; any other failure must
      also fail in prod before it is called unrelated.

- [ ] **Step 3: Reconcile** with the BigQuery MCP against the dev models:

  - Schools rows equal `count(*)` of scores with SGP in
    `int_assessments__state_nj_scores`; 0 null `location_key`.
  - Teachers: scores with `window_day_count` 0 or null (expect 0); teacher-role-
    subject combinations versus the mockup's 272 (spec _Appendix_). Report the
    difference, and explain 3 sampled differences as school-day counting or the
    per-teacher student rule; any other cause is a bug.
  - Access: every ES and MS `location_key` in the schools model has at least 1
    access row; list any that do not.

- [ ] **Step 4: Lint.** With cwd `W2`:
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <every changed file> </dev/null 2>&1 | tail -n 30`.
      Fix findings; commit with `git -C W2 add -u`.

- [ ] **Step 5: Push and open the PR.** Template and plain-language rules as in
      PR 1. Title `feat(dbt): add the SGP dashboard report models`. Body:
      `Refs #6279`; the A2 exception with a link to #6480; the Step 3 results
      (counts only, no names); Reviewer Notes on the matching rules and the
      `format: sql` fixtures. Read the PR back and confirm. Offer to watch CI
      and answer the `claude-review` findings (root CLAUDE.md).

After merge: write the workbook plan (`tableau-workbook-xml` skill) against the
prod models, and add the workbook's `asset.metadata.id` to the exposure once it
is published.

## Revision 2026-11-24, after PR 1 merged

- PR 1 found that Paterson's Cambium file has no economic disadvantage status
  for any student and leaves `nj_ml_status` blank for most students its own
  `multilingual_learner` flag marks Y. The requester compared the counts and
  chose: multilingual learners from the flag (`aligned_ml_status`), the same
  rule as STAT; economic disadvantage null where the file has none, shown as
  `Not reported`. Task 1 now adds only the economic status; Task 2's interface
  carries `is_multilingual_learner`.
- Task 0 found that CI's `zz_stg_kipptaf_cambium.int_cambium__all_assessments`
  is a `select *` view over prod, so it returns the new column and no staging
  write is needed; mocks of that model use `format: sql`.
