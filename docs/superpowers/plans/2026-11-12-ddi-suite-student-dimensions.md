# DDI Suite student dimensions in Cube: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put every DDI Suite student dimension still missing from
`student_assessment_scores_view` into the marts and Cube: the school week, 3
per-student flags, the homeroom name and section number, and 3 subject-picked
flags.

**Architecture:** All new dbt columns land on `dim_student_enrollment_status` (1
row per enrollment stint), copied from the extract models the DDI Suite reads
today, joined on `student_enrollment_key`. Cube exposes them through the
existing `student_enrollment_status` cube; the 3 per-subject members live on the
`student_assessment_scores` cube next to #6305's `bucket` and pick the ELA or
math column by `bucket_subject`.

**Tech Stack:** dbt (kipptaf, BigQuery), dbt unit tests, Cube YAML,
`tests/cube/test_cube_schema.py` (pytest + Cube compile), BigQuery MCP for
acceptance queries.

**Spec:**
`docs/superpowers/specs/2026-11-11-ddi-suite-student-dimensions-design.md`

## Global Constraints

- Worktree `<wt>` =
  `/workspaces/teamster/.claude/worktrees/cristinabaldor/feat/claude-ddi-student-flags`.
  Use `git -C <wt>` and absolute `<wt>/...` paths; run dbt and pytest through
  `uv run`. Invoke the `dbt-local-dev` skill before the first dbt build.
- Copy the dashboard: every value equals what the extract model holds for that
  stint today. No "as of assessment date" logic, no coalescing beyond what the
  extract already does.
- New dbt columns are column-level `config.meta.contains_pii: true`, with a
  `description:` and `data_type`. The model is contract-enforced.
- dbt column names (final): `is_sipps`, `is_tutoring`, `is_self_contained`,
  `homeroom_name`, `homeroom_section_number`, `is_ela_low_25`, `is_math_low_25`,
  `ela_state_test_proficiency`, `math_state_test_proficiency`,
  `dibels_most_recent_composite`.
- View member names (final): the 5 per-student names above, plus `is_low_25`,
  `state_test_proficiency`, `dibels_most_recent_composite`,
  `school_week_start_date`, `school_week_end_date`.
- The ELA/math pair members on the `student_enrollment_status` cube are
  `public: false`. No member goes on any view other than
  `student_assessment_scores_view`. No member joins the `proficiency_rollup`
  pre-aggregation.
- One-column Cube members get a description identical to their dbt column and a
  `TWINS` entry in `tests/cube/test_cube_schema.py`.
- No student value (name, number, id, row) in a commit message, PR body or issue
  comment.

Commands, referred to below by name:

- **DEV BUILD `<selection>`**:
  `uv run dbt build --project-dir <wt>/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod --select <selection> 2>&1 | tail -n 30`
- **UNIT `<model>`**: the same flags with `dbt test` and
  `--select "test_type:unit,<model>"`.
- **CUBE TESTS**: `cd <wt> && uv run pytest tests/cube/ -q 2>&1 | tail -n 20`.
  Run `npm ci` in `<wt>/src/cube` once first; check the summary shows no skipped
  compile test.
- **LINT `<files>`**: from `<wt>`,
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`.

## Review Focus

1. A `student_number` that repeats in 2 regions must take only its own region's
   flags. The key includes `_dbt_source_project`; Task 2's unit test pins it
   with a same-number row in another region.
2. A student with 2 stints in 1 year gets each stint's own extract values and no
   extra rows. Task 2's unit test pins it; the dim's `unique` PK test backs it.
3. Miami `is_self_contained` stays null (the extract's value), not false. Task
   2's unit test pins it.
4. A Math assessment shows `No Composite Score Available` for DIBELS, and a
   science assessment shows null for all 3 subject members. Task 5 pins both
   with a compiled-SQL check.
5. A stint with no extract row (for example a grade 99 placeholder) gets null
   flags, not a dropped dim row. Task 2's and Task 4's unit tests pin it.

---

### Task 1: School week on the assessment view

**Files:**

- Modify:
  `src/cube/model/views/student_assessments/student_assessment_scores_view.yml`
  (the `student_assessment_scores.dates` include and the `Date` folder)
- Test: `tests/cube/test_cube_schema.py`

**Interfaces:**

- Produces: `DDI_SUITE_VIEW_MEMBERS`, a module-level list in
  `tests/cube/test_cube_schema.py`, and
  `test_assessment_view_exposes_ddi_suite_members()`. Later tasks append to the
  list.

- [ ] **Step 1: Write the failing test.** Add to
      `tests/cube/test_cube_schema.py` a list
      `DDI_SUITE_VIEW_MEMBERS = ["school_week_start_date", "school_week_end_date"]`
      (bare names: the view's `dates` include has no `prefix`) and a test that
      compiles the model the way `test_model_compiles_with_cube` does and
      asserts every name is a dimension of `student_assessment_scores_view`.
- [ ] **Step 2: Run it to see it fail.** CUBE TESTS. Expected: the new test
      FAILs naming both members.
- [ ] **Step 3: Add both members** to the `dates` include and the `Date` folder.
- [ ] **Step 4: Run it to see it pass.** CUBE TESTS. Expected: all PASS.
- [ ] **Step 5: Lint and commit.** LINT the 2 files, then commit them by name:
      `feat(cube): add the school week to the assessment-scores view`.

### Task 2: Per-student flags and homeroom on `dim_student_enrollment_status`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_student_enrollment_status.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_enrollment_status.yml`

**Interfaces:**

- Consumes: `int_extracts__student_enrollments` columns `student_number`,
  `_dbt_source_project`, `academic_year`, `entrydate`, `is_sipps`,
  `is_tutoring`, `is_self_contained`, `advisory_name`, `team` (which is
  `advisory_section_number`).
- Produces: dim columns `is_sipps` (bool), `is_tutoring` (bool),
  `is_self_contained` (bool), `homeroom_name` (string),
  `homeroom_section_number` (string).

- [ ] **Step 1: Write the failing unit test**
      `unit_dim_student_enrollment_status_student_flags` in the properties yml.
      Give `dim_student_enrollments` as `format: sql` rows whose keys are the
      surrogate hash, built in the fixture as
      `to_hex(md5(concat(<student_number>, '-', <project>, '-', <year>, '-', <entrydate>)))`
      (the `student_enrollment_key` macro is `generate_surrogate_key` over those
      4, cast to string). Rows:
  - NJ stint A (`kippnewark`, student 1001, 2026, entry 2026-09-02): extract row
    `is_sipps` true, `is_tutoring` true, `is_self_contained` true,
    `advisory_name` `Harvard`, `team` `5HAR`.
  - Same student 1001 in `kippmiami`, 2026: extract row with all 3 flags false,
    `is_self_contained` null, `advisory_name` `Rm 12`, `team` `HR12`.
  - NJ student 1002 with 2 stints in 2026 (entry 2026-09-02 and 2027-01-10),
    each with its own extract row, differing `team`.
  - NJ stint with no extract row. Give every other input `rows: []`. Expect each
    stint's own values, and nulls on the no-extract stint. Add
    `int_extracts__student_enrollments` (and, so Task 4 doesn't break it,
    `int_extracts__student_enrollments_subjects`) with `rows: []` to the
    existing `unit_dim_student_enrollment_status_buckets` test.
- [ ] **Step 2: Run it to see it fail.** UNIT `dim_student_enrollment_status`.
      Expected: FAIL; the new columns do not exist.
- [ ] **Step 3: Implement.** Add a CTE over `int_extracts__student_enrollments`
      that builds `student_enrollment_key` with the macro (same call shape as
      `section_504`) and selects the 5 source columns; left join it on
      `student_enrollment_key`; select the 5 columns renamed as in Interfaces.
      Add the 5 contract columns to the yml, each with `data_type`,
      `description:` (what the DDI Suite shows, from the spec's workstream 3
      table) and `config.meta.contains_pii: true`. Update the model
      `description:` to name the new columns' source.
- [ ] **Step 4: Run it to see it pass.** UNIT `dim_student_enrollment_status`.
      Expected: both unit tests PASS.
- [ ] **Step 5: Build.** DEV BUILD `dim_student_enrollment_status`. Expected:
      PASS, including the `unique` PK test.
- [ ] **Step 6: Acceptance query.** On the dev build, count 2026 stints where
      each of the 5 columns differs from `int_extracts__student_enrollments`
      (joined by the reproduced key). Expected: 0 for every column.
- [ ] **Step 7: Lint and commit.** LINT the 2 files; commit by name:
      `feat(dbt): add DDI Suite student flags and homeroom to the enrollment status dim`.

### Task 3: Per-student flags and homeroom in Cube

**Files:**

- Modify: `src/cube/model/cubes/students/student_enrollment_status.yml`
- Modify:
  `src/cube/model/views/student_assessments/student_assessment_scores_view.yml`
  (the `student_enrollment_status` include and the `Status` folder)
- Modify: `tests/cube/test_cube_schema.py` (`TWINS`, `DDI_SUITE_VIEW_MEMBERS`)

**Interfaces:**

- Consumes: Task 2's 5 dim columns; Task 1's `DDI_SUITE_VIEW_MEMBERS`.
- Produces: public members `student_enrollment_status.is_sipps`, `is_tutoring`,
  `is_self_contained`, `homeroom_name`, `homeroom_section_number`.

- [ ] **Step 1: Write the failing tests.** Append the 5 names to
      `DDI_SUITE_VIEW_MEMBERS`; add 5 `TWINS` entries
      `("student_enrollment_status", <col>): ("dim_student_enrollment_status", <col>)`.
- [ ] **Step 2: Run them to see them fail.** CUBE TESTS. Expected: the view test
      and the twin test FAIL on the 5 names.
- [ ] **Step 3: Add the 5 members** to the cube (`public: true`, description
      copied verbatim from the dbt yml), then to the view include and the
      `Status` folder. Add `ai_context` to `is_tutoring` saying it reads today's
      date, so past years read false.
- [ ] **Step 4: Run them to see them pass.** CUBE TESTS. Expected: all PASS.
- [ ] **Step 5: Lint and commit.** LINT the 3 files; commit by name:
      `feat(cube): add DDI Suite student flags and homeroom to the assessment-scores view`.

### Task 4: Per-subject flags on `dim_student_enrollment_status`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_student_enrollment_status.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_enrollment_status.yml`

**Interfaces:**

- Consumes: `int_extracts__student_enrollments_subjects` columns
  `student_number`, `_dbt_source_project`, `academic_year`, `entrydate`,
  `discipline` (`ELA` or `Math`), `is_low_25_fl`, `state_test_proficiency`,
  `dibels_most_recent_composite`.
- Produces: `is_ela_low_25` (bool), `is_math_low_25` (bool),
  `ela_state_test_proficiency` (string), `math_state_test_proficiency` (string),
  `dibels_most_recent_composite` (string, from the `ELA` row).

- [ ] **Step 1: Write the failing unit test**
      `unit_dim_student_enrollment_status_subject_flags`, same key-fixture
      approach as Task 2. Rows: 1 NJ stint with an `ELA` row (`is_low_25_fl`
      false, `state_test_proficiency` `Met Expectations`,
      `dibels_most_recent_composite` `At Benchmark`) and a `Math` row
      (`is_low_25_fl` false, `Partially Met`, `No Composite Score Available`); 1
      Miami stint with `ELA` `is_low_25_fl` true and `Math` false; 1 stint with
      no subject rows. Expect the pairs per stint, DIBELS from the `ELA` row,
      nulls on the no-row stint. Add
      `int_extracts__student_enrollments_subjects` with `rows: []` to Task 2's
      unit test if not already there.
- [ ] **Step 2: Run it to see it fail.** UNIT `dim_student_enrollment_status`.
      Expected: FAIL.
- [ ] **Step 3: Implement.** 1 CTE over the subjects model building the key,
      pivoting by `discipline` into the 5 columns (conditional aggregation
      grouped by key, or 2 filtered left joins; the model's grain test,
      `student_number` x `academic_year` x `entrydate` x `iready_subject`, makes
      either 1 row per key and subject). Left join on the key. Add the 5
      contract columns to the yml as in Task 2.
- [ ] **Step 4: Run it to see it pass.** UNIT `dim_student_enrollment_status`.
      Expected: all 3 unit tests PASS.
- [ ] **Step 5: Build.** DEV BUILD `dim_student_enrollment_status`. Expected:
      PASS.
- [ ] **Step 6: Acceptance query.** On the dev build, count 2026 stints where
      each pair column differs from the subjects model's matching `discipline`
      row. Expected: 0 for every column.
- [ ] **Step 7: Lint and commit.** LINT the 2 files; commit by name:
      `feat(dbt): add DDI Suite subject flags to the enrollment status dim`.

### Task 5: Subject-picked flags in Cube (after #6305)

**Files:**

- Modify: `src/cube/model/cubes/students/student_enrollment_status.yml`
- Modify:
  `src/cube/model/cubes/student_assessments/student_assessment_scores.yml`
- Modify:
  `src/cube/model/views/student_assessments/student_assessment_scores_view.yml`
- Modify: `tests/cube/test_cube_schema.py`

**Interfaces:**

- Consumes: Task 4's 5 dim columns; #6305's `student_assessments.bucket_subject`
  (`Reading`, `Math`, or null) and the `bucket` member's pattern on
  `student_assessment_scores`.
- Produces: public members `student_assessment_scores.is_low_25`,
  `state_test_proficiency`, `dibels_most_recent_composite`.

- [ ] **Step 1: Bring in #6305.** If #6305 is not on `origin/main`, stop and ask
      the user before going on. Otherwise invoke `resuming-a-branch`, then merge
      `origin/main` into the branch.
- [ ] **Step 2: Write the failing tests.** Append `is_low_25`,
      `state_test_proficiency`, `dibels_most_recent_composite` to
      `DDI_SUITE_VIEW_MEMBERS`; add 5 `TWINS` entries for the private pair
      members. Add a test that compiles the model and asserts the compiled SQL
      of `student_assessment_scores.dibels_most_recent_composite` contains the
      literal `'No Composite Score Available'` under the `'Math'` branch and has
      no `ELSE` branch (so other subjects return null).
- [ ] **Step 3: Run them to see them fail.** CUBE TESTS. Expected: FAIL.
- [ ] **Step 4: Implement.** Add the 5 pair members to
      `student_enrollment_status` as `public: false`. Add the 3 members to
      `student_assessment_scores` next to `bucket`, each
      `CASE {student_assessments.bucket_subject} WHEN 'Reading' THEN ... WHEN 'Math' THEN ... END`
      (DIBELS's Math branch is the literal). Descriptions say what the member
      means for an assessment row; `ai_context` says the subject comes from
      `bucket_subject` and that Low 25 is Miami only. Add the 3 to the view's
      top-cube include and the `Status` folder.
- [ ] **Step 5: Run them to see them pass.** CUBE TESTS. Expected: all PASS.
- [ ] **Step 6: Lint and commit.** LINT the 4 files; commit by name:
      `feat(cube): add DDI Suite subject flags to the assessment-scores view`.

### Task 6: Verify the branch and open the PR

**Files:**

- Modify: the DDI Suite validation spec on the #5668 validation branch (via the
  `cube-validation` skill), only if that branch is reachable; otherwise record
  the comparisons to add in the PR body.

- [ ] **Step 1: Full checks.** DEV BUILD `dim_student_enrollment_status`, UNIT
      `dim_student_enrollment_status`, CUBE TESTS. Expected: all PASS.
- [ ] **Step 2: Lint everything changed.** LINT every file in
      `git -C <wt> diff --name-only origin/main...HEAD`. Expected: no findings.
- [ ] **Step 3: Validation comparisons.** Invoke `cube-validation`. Add
      comparisons for sheets filtered or split by each new member, each with a
      `rows:` block, and record the reuse mappings (`module_number` ->
      `module_code`, `is_normed_scope` -> `is_internal_assessment`). Expected
      differences are only those in the spec's _Differences to accept_.
- [ ] **Step 4: Open the PR.** Push, open the PR from
      `.github/pull_request_template.md` with `Closes #6372` and `Refs #6192`,
      and note in Reviewer Notes that the school week moved out of PR D. Comment
      on #6192 that PR D no longer carries `dates.school_week_start_date`. Then
      offer CI watch and `claude-review` follow-up per root CLAUDE.md.
