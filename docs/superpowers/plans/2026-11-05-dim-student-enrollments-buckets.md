# ELA and math buckets in the marts: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put each student's ELA and math bucket on `dim_student_enrollments`,
Miami's archived buckets in `int_students__bucket_assignments`, and a
`bucket_subject` on `dim_assessments`, so the next PR can expose a
subject-matched bucket in Cube.

**Architecture:** The Miami PowerSchool archive joins the kipptaf
`int_powerschool__spenrollments` union. The bucket model resolves Miami archive
`studentid`s through `int_powerschool__ada`. The enrollment dimension joins the
bucket model once per subject and applies the 2025 rule. Internal assessments
get `bucket_subject` from the course subject crosswalk in
`int_assessments__assessments_members`; other families map it in their
`dim_assessments` branch. This is the type 3 (dbt) PR; Cube follows in a
separate branch that refs #6192.

**Tech Stack:** dbt (kipptaf project, BigQuery), dbt unit tests, BigQuery MCP
for acceptance queries.

**Spec:**
`docs/superpowers/specs/2026-10-26-dim-student-enrollments-buckets-design.md`,
including its "Revision 2026-10-29" section.

## Global Constraints

- The rule, per column: `academic_year >= 2025` with a stored bucket gives the
  stored bucket; `academic_year >= 2025` with none gives `Bucket 4`;
  `academic_year < 2025` gives null; `grade_level = 99` gives null.
- Column names `ela_bucket` and `math_bucket`, `data_type: string`, column-level
  `config.meta.contains_pii: true`.
- One value per enrollment row; the bucket model's latest-assignment pick
  decides the value. No key or hash changes on any mart.
- `bucket_subject` values: `Reading`, `Math`, or null.
- The Miami archive branch (academic years 2024 and 2025) and the Focus branch
  (2026 on) must not overlap on `academic_year`; the bucket model's grain test
  catches an overlap.
- Out of scope: the `nj_student_tier` rule in
  `int_extracts__student_enrollments_subjects`, every Cube file, and NJ
  Tutoring.
- Worktree `<wt>` =
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-dim-student-enrollments-buckets`.
  Run every command from `/workspaces/teamster` with absolute `<wt>` paths, dbt
  through `uv run`, and
  `--state /workspaces/teamster/src/dbt/kipptaf/target/prod`.
- No student value (name, number, id, row) in a commit message or the PR body.

Dev build command, referred to below as **DEV BUILD `<selection>`**:

```bash
uv run dbt build --project-dir <wt>/src/dbt/kipptaf --target dev --defer \
  --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --select <selection> 2>&1 | tail -n 30
```

Unit-test command, **UNIT `<model>`**: the same flags with `dbt test` and
`--select "test_type:unit,<model>"`.

## Review Focus

1. A Miami archive `studentid` with no `int_powerschool__ada` row drops its
   bucket silently. Task 2 pins it with a unit-test row and an acceptance query
   that every archived bucket student reaches the model.
2. A `student_number` that repeats in 2 regions must take only its own region's
   bucket. Task 3 pins it with a unit-test row.
3. A student with 2 enrollment stints in 1 year gets the same bucket on both
   rows and no extra rows. Task 3 pins it with a unit-test row; the dimension's
   `unique` key test backs it.
4. An assessment subject with no crosswalk row (`Word Work`), or with a trailing
   space (`AP Calculus `), gets a null `bucket_subject`, as the dashboards give
   it no tier. Task 4 pins the no-row case with a unit-test row.
5. A crosswalk subject that maps to 2 disciplines would fan out the members
   model. The members grain test and the `dim_assessments` `unique` key test
   catch it; Task 4 runs both.

---

### Task 1: Miami archive into the spenrollments union

**Files:**

- Modify: `<wt>/src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml`
- Modify:
  `<wt>/src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__spenrollments.sql`

**Interfaces:**

- Produces: `ref("int_powerschool__spenrollments")` returns Miami archive rows
  with `_dbt_source_project = 'kippmiami'` (academic years 2020, 2024 and 2025;
  specprog names `Bucket 1/2/3 - ELA|Math` and `Remote Instruction`).

- [ ] **Step 1: Declare the source.** Add `int_powerschool__spenrollments` to
      the `kippmiami_powerschool` tables list, with the same
      `config.meta.dagster` block as its siblings (`group: powerschool`,
      `asset_key:     [kippmiami, powerschool, int_powerschool__spenrollments]`).
      In the source description, change "16 permanent tables" to 17 and add
      special programs (the bucket assignments) to the list of what the archive
      holds.

- [ ] **Step 2: Union it.** Add
      `source("kippmiami_powerschool", "int_powerschool__spenrollments")` to the
      `relations` list, after `kippcamden` and before `kipppaterson`, matching
      `int_powerschool__ada.sql`.

- [ ] **Step 3: Confirm no other consumer changes.** Re-run this query.
      Expected: only `Bucket %` and `Remote Instruction` names. Any
      `Attendance Exceptions`, `MTSS%` or `High School%` name means a consumer
      that joins through `int_powerschool__ada` could change: stop and report.

```sql
select specprog_name, academic_year, count(*) as n
from kippmiami_powerschool.int_powerschool__spenrollments
group by 1, 2
```

- [ ] **Step 4: Build.** DEV BUILD `int_powerschool__spenrollments`. Expected:
      PASS. The NJ sources resolve to your `zz_<user>_<district>_powerschool`
      clones; if the build reports a missing NJ relation, refresh it with
      `uv run dbt clone --project-dir /workspaces/teamster/src/dbt/<district> --target dev --state /workspaces/teamster/src/dbt/<district>/target/prod --select int_powerschool__spenrollments --full-refresh`.
      Then count dev rows where `_dbt_source_project = 'kippmiami'`. Expected:
      2,574, the archive's row count.

- [ ] **Step 5: Commit.**
      `git -C <wt> add -u && git -C <wt> commit -m "feat(dbt): union Miami's archived special programs into kipptaf spenrollments"`

### Task 2: Miami archive branch in the bucket model

**Files:**

- Modify:
  `<wt>/src/dbt/kipptaf/models/students/intermediate/int_students__bucket_assignments.sql`
- Modify:
  `<wt>/src/dbt/kipptaf/models/students/intermediate/properties/int_students__bucket_assignments.yml`

**Interfaces:**

- Consumes: Task 1's Miami rows; `ref("int_powerschool__ada")` (`studentid`,
  `student_number`, `_dbt_source_project`).
- Produces: unchanged columns; new rows with
  `_dbt_source_project = 'kippmiami'`, `bucket_store = 'powerschool'`, academic
  years 2024 and 2025.

- [ ] **Step 1: Extend the unit test.** In
      `unit_int_students__bucket_assignments`:
  - Add 2 `int_powerschool__spenrollments` rows with
    `_dbt_source_project: kippmiami` and a kippmiami `_dbt_source_relation` in
    the existing rows' form: `studentid: 21`, `academic_year: 2025`,
    `Bucket 1 - ELA`, `enter_date: 2025-09-15`, `exit_date: 2026-06-30`; and
    `studentid: 22`, `academic_year: 2025`, `Bucket 2 - Math`, same dates (no
    ada row, so it must drop).
  - Add the input `ref("int_powerschool__ada")` with 2 rows: `studentid: 21`,
    `student_number: 84005678`, `_dbt_source_project: kippmiami`; and
    `studentid: 11`, `student_number: 9999`, `_dbt_source_project: kippnewark`
    (an NJ ada row must not replace the enrollment-resolved number).
  - Add the expected row: `academic_year: 2025`,
    `_dbt_source_project: kippmiami`, `student_number: 84005678`,
    `subject: Reading`, `bucket: Bucket 1`, `bucket_store: powerschool`,
    `assignment_date: 2025-09-15`, `n_active_assignments: 0`. The 3 existing
    expected rows stay as they are.
  - Update the test description to name the archive branch and the dropped
    unmapped row.

- [ ] **Step 2: Run it to see it fail.** UNIT
      `int_students__bucket_assignments`. Expected: FAIL. The kippmiami row is
      missing from actual.

- [ ] **Step 3: Implement.** In the SQL:
  - Add a CTE `miami_archive_student_numbers`: grain-projection
    `select distinct studentid, student_number, _dbt_source_project` from
    `int_powerschool__ada` where `_dbt_source_project = 'kippmiami'`, annotated
    `grain projection, not dup-masking` with the reason that each archive
    `studentid` maps to 1 `student_number`.
  - In `powerschool_programs`, make the `int_extracts__student_enrollments` join
    a `left join` and move `co.rn_year = 1` into its `on`. Add a
    `left join miami_archive_student_numbers as an` on `studentid` and
    `_dbt_source_project`. Select
    `coalesce(co.student_number, an.student_number) as student_number`.
  - In `assignment_union`'s PowerSchool branch, add
    `where student_number is not null`. This keeps the old inner-join drop for
    rows that match neither path.
  - Update the model description: PowerSchool special programs (NJ), the frozen
    Miami PowerSchool archive (2024-25 and 2025-26, matched to student numbers
    through the archive's ADA rows), and Focus custom student groups (Miami from
    2026-27).

- [ ] **Step 4: Run it to see it pass.** UNIT
      `int_students__bucket_assignments`. Expected: PASS.

- [ ] **Step 5: Build and check coverage.** DEV BUILD
      `int_students__bucket_assignments`. Expected: PASS, including the grain
      test. Then compare the dev model with the archive's distinct bucketed
      students, per year and subject. Expected: `n_model = n_archive` on all 4
      rows (2024 and 2025, Reading and Math).

```sql
with
    archive as (
        select
            academic_year,
            if(specprog_name like '%ELA', 'Reading', 'Math') as `subject`,
            count(distinct studentid) as n_archive,
        from kippmiami_powerschool.int_powerschool__spenrollments
        where specprog_name like 'Bucket%'
        group by 1, 2
    ),
    model as (
        select academic_year, `subject`, count(*) as n_model,
        from zz_<user>_kipptaf_students.int_students__bucket_assignments
        where _dbt_source_project = 'kippmiami' and academic_year in (2024, 2025)
        group by 1, 2
    )
select * from archive full join model using (academic_year, `subject`)
```

- [ ] **Step 6: Commit.**
      `git -C <wt> add -u && git -C <wt> commit -m "feat(dbt): read Miami's archived buckets in int_students__bucket_assignments"`

### Task 3: `ela_bucket` and `math_bucket` on `dim_student_enrollments`

**Files:**

- Modify:
  `<wt>/src/dbt/kipptaf/models/marts/dimensions/dim_student_enrollments.sql`
- Modify:
  `<wt>/src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_enrollments.yml`

**Interfaces:**

- Consumes: `ref("int_students__bucket_assignments")` (`academic_year`,
  `_dbt_source_project`, `student_number`, `subject`, `bucket`).
- Produces: `ela_bucket string`, `math_bucket string` on
  `dim_student_enrollments`. The Cube PR reads both.

- [ ] **Step 1: Write the unit test** `unit_dim_student_enrollments_buckets`.
      Inputs: `int_students__student_enrollment_union` (dict rows with
      `student_number`, `_dbt_source_project`, `academic_year`, `entrydate`,
      `exitdate`, `schoolid`, `grade_level`), `int_students__schools`
      (`rows: []`), and `int_students__bucket_assignments` with 3 rows:
      `(2025, kippnewark, 5001, Reading, Bucket 2)`,
      `(2025, kippcamden, 5001, Math, Bucket 1)` and
      `(2024, kippnewark, 5002, Reading, Bucket 2)`. Expect these rows, each
      asserting `academic_year`, `entry_date_key`, `grade_level`, `ela_bucket`
      and `math_bucket`:

| Enrollment row                                    | `ela_bucket` | `math_bucket` |
| ------------------------------------------------- | ------------ | ------------- |
| 5001, kippnewark, 2025, grade 5, entry 2025-09-03 | Bucket 2     | Bucket 4      |
| 5001, kippnewark, 2025, grade 5, entry 2026-01-12 | Bucket 2     | Bucket 4      |
| 5001, kippcamden, 2025, grade 6                   | Bucket 4     | Bucket 1      |
| 5002, kippnewark, 2024, grade 4                   | null         | null          |
| 5003, kippnewark, 2026, grade 99                  | null         | null          |
| 5004, kippnewark, 2026, grade 12                  | Bucket 4     | Bucket 4      |

- [ ] **Step 2: Run it to see it fail.** UNIT `dim_student_enrollments`.
      Expected: FAIL. The columns do not exist yet.

- [ ] **Step 3: Implement.** Left join `int_students__bucket_assignments` twice,
      as `rb` with `rb.subject = 'Reading'` and as `mb` with
      `mb.subject = 'Math'` in the `on`. Join on `student_number`,
      `academic_year` and `_dbt_source_project`. Select
      `if(enr.academic_year >= 2025 and enr.grade_level != 99, coalesce(rb.bucket, 'Bucket 4'), null) as ela_bucket`,
      and the same with `mb` for `math_bucket`. Put a one-line comment above the
      first naming 2025 as the year the 4-bucket model started (S20). Add both
      columns to the YAML with `data_type: string` and
      `config.meta.contains_pii: true`. Their descriptions say: the student's
      ELA (or math) bucket for the year, the latest stored one or `Bucket 4`
      when none is stored; null before 2025-26 and on grade 99 rows; the same on
      every enrollment row of the year; and to pick the bucket that matches the
      subject being analyzed (for assessments, the assessment's
      `bucket_subject`).

- [ ] **Step 4: Run it to see it pass.** UNIT `dim_student_enrollments`.
      Expected: PASS.

- [ ] **Step 5: Build and check the rule.** DEV BUILD
      `int_students__bucket_assignments dim_student_enrollments`. Expected:
      PASS. Then, on the dev view, count non-null buckets where
      `academic_year < 2025` or `grade_level = 99` (expected 0), and null
      buckets where `academic_year >= 2025` and `grade_level != 99` (expected
      0).

- [ ] **Step 6: Commit.**
      `git -C <wt> add -u && git -C <wt> commit -m "feat(dbt): add ela_bucket and math_bucket to dim_student_enrollments"`

### Task 4: `bucket_subject` in `int_assessments__assessments_members`

**Files:**

- Modify:
  `<wt>/src/dbt/kipptaf/models/assessments/intermediate/int_assessments__assessments_members.sql`
- Modify:
  `<wt>/src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__assessments_members.yml`

**Interfaces:**

- Consumes: `ref("stg_google_sheets__assessments__course_subject_crosswalk")`
  (`Illuminate_Subject_Area`, `Discipline`).
- Produces: `bucket_subject string` (`Reading`, `Math`, null) on every members
  row. Task 5 reads it.

- [ ] **Step 1: Write the unit test**
      `test_bucket_subject_from_course_subject_crosswalk`. Mock the same 4
      inputs as `test_apex_assessments_are_their_own_canonical`. Give Illuminate
      assessments 9101 `Text Study`, 9102 `Algebra I`, 9103 `Science` and 9104
      `Word Work`, and an Apex assessment 9201 `Text Study` (academic year
      2026). Add the crosswalk input (dict) with rows
      `(PowerSchool, ENG10, Text Study, ELA)`,
      `(PowerSchool, MATH30, Algebra I, Math)`,
      `(PowerSchool, SCI10, Science, Science)` and a Focus row with a null
      `Illuminate_Subject_Area`. Columns: `SIS`, `PowerSchool_Course_Number`,
      `Illuminate_Subject_Area`, `Discipline`, plus `Standard_Course_Name`,
      which is not null. Expect `source`, `assessment_id`, `subject_area` and
      `bucket_subject`: 9101 Reading, 9102 Math, 9103 null, 9104 null, and apex
      9201 Reading.

- [ ] **Step 2: Add the crosswalk input to the 2 existing members unit tests**
      as `rows: []`.

- [ ] **Step 3: Run them to see the new one fail.** UNIT
      `int_assessments__assessments_members`. Expected: the new test FAILs; the
      2 existing tests PASS.

- [ ] **Step 4: Implement.** Add a CTE `subject_disciplines`: grain-projection
      `select distinct Illuminate_Subject_Area as subject_area, Discipline as discipline`
      where `Illuminate_Subject_Area is not null`, annotated with the reason
      that the crosswalk maps each subject to 1 discipline. In the final select,
      alias `canonical as c`, prefix its columns with `c.`, left join
      `subject_disciplines as sd` on `subject_area`, and add, last,
      `case sd.discipline when 'ELA' then 'Reading' when 'Math' then 'Math' end as bucket_subject`.
      Add the YAML column. Its description says `Reading` or `Math` when the
      course subject crosswalk maps `subject_area` to the ELA or Math
      discipline, and null otherwise, including subjects with no crosswalk row.

- [ ] **Step 5: Run them to see them pass.** UNIT
      `int_assessments__assessments_members`. Expected: 3 PASS.

- [ ] **Step 6: Build.** DEV BUILD `int_assessments__assessments_members`.
      Expected: PASS, including the `source` x `assessment_id` grain test.

- [ ] **Step 7: Commit.**
      `git -C <wt> add -u && git -C <wt> commit -m "feat(dbt): map internal assessments to a bucket subject"`

### Task 5: `bucket_subject` on `dim_assessments`

**Files:**

- Modify: `<wt>/src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql`
- Modify:
  `<wt>/src/dbt/kipptaf/models/marts/dimensions/properties/dim_assessments.yml`

**Interfaces:**

- Consumes: Task 4's `int_assessments__assessments_members.bucket_subject`.
- Produces: `bucket_subject string` on `dim_assessments`. The Cube PR's `bucket`
  dimension reads it.

- [ ] **Step 1: Write the unit test** `test_bucket_subject_by_family`. Inputs:
      `int_assessments__assessments_members` as `format: sql`, because the
      column is new in this PR and dict format would introspect prod. Give it 2
      internal Illuminate rows: 9101 `Text Study` with `bucket_subject` Reading,
      and 9103 `Science` with null. Mock
      `int_assessments__assessments_canonical` to match. Give
      `int_iready__diagnostic_results` rows for Math and Reading with a scale
      score, and `int_assessments__college_assessment` 1 SAT EBRW row with
      `course_discipline: ENG`. The other 6 inputs get `rows: []`. Expect
      `type`, `academic_subject` and `bucket_subject`: (illuminate, Text Study,
      Reading), (illuminate, Science, null), (iready, Math, Math), (iready,
      Reading, Reading), (college, EBRW, Reading).

- [ ] **Step 2: Run it to see it fail.** UNIT `dim_assessments`. Expected: FAIL.

- [ ] **Step 3: Implement.** Append `bucket_subject` to `union_cols`, add it to
      every branch as the table below gives, and select it in the final select.
      Add the YAML column (`data_type: string`). Its description says which
      bucket applies to scores on the assessment: `Reading` pairs with
      `ela_bucket`, `Math` with `math_bucket`, and null when none applies
      (science, social studies, AP, and internal subjects with no course subject
      crosswalk row). It also says where each family's value comes from.

| Branch                                         | `bucket_subject` expression                                                    |
| ---------------------------------------------- | ------------------------------------------------------------------------------ |
| `illuminate_assessments`                       | `m.bucket_subject`                                                             |
| `state_nj_assessments`, `state_fl_assessments` | `case discipline when 'ELA' then 'Reading' when 'Math' then 'Math' end`        |
| `iready_assessments`                           | `subject` (already `Reading` or `Math`)                                        |
| `star_assessments`                             | `if(star_subject = 'Math', 'Math', 'Reading')`                                 |
| `dibels_assessments`                           | `'Reading'`                                                                    |
| `college_assessments`                          | `case course_discipline when 'ENG' then 'Reading' when 'MATH' then 'Math' end` |
| `practice_assessments`, `ap_assessments`       | `cast(null as string)`                                                         |

- [ ] **Step 4: Run it to see it pass.** UNIT `dim_assessments`. Expected: PASS.

- [ ] **Step 5: Build and check coverage.** DEV BUILD
      `int_assessments__assessments_members dim_assessments`. Expected: PASS,
      including the `unique` test on `assessment_key`. Then count dev rows by
      `type` x `bucket_subject`. Expected: `Text Study` and `Mathematics` are
      always Reading and Math; Science and Social Studies are always null;
      `Algebra I MS` is Math.

- [ ] **Step 6: Commit.**
      `git -C <wt> add -u && git -C <wt> commit -m "feat(dbt): add bucket_subject to dim_assessments"`

### Task 6: Verify the branch and open the PR

**Files:** none modified. The PR body comes from
`.github/pull_request_template.md`.

- [ ] **Step 1: Build every changed model together.** DEV BUILD
      `int_powerschool__spenrollments int_students__bucket_assignments dim_student_enrollments int_assessments__assessments_members dim_assessments`.
      Expected: PASS. A full `<model>+` build would rebuild the assessment star
      and most extracts. dbt Cloud CI runs `state:modified+`, which covers them.

- [ ] **Step 2: Run downstream unit tests.** The DEV BUILD flags with
      `dbt test --select "test_type:unit,int_powerschool__spenrollments+ test_type:unit,int_assessments__assessments_members+"`.
      Expected: PASS.

- [ ] **Step 3: Spec acceptance query.** For `academic_year >= 2025`, compare
      the dev `dim_student_enrollments` buckets with prod
      `int_extracts__student_enrollments_subjects.nj_student_tier`, at student,
      year and subject grain (`iready_subject` Reading ↔ `ela_bucket`). Use
      `rn_year = 1` rows and group the counts by region and match or mismatch.
      Expected: NJ matches everywhere. Miami 2025 differs only where prod still
      fills `Bucket 4` for a student with an archived bucket; prod has not read
      the archive yet.

- [ ] **Step 4: Lint.** From `<wt>`:
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <the 9 changed files> </dev/null`.
      Expected: no lint findings. Formatting is the commit hook's job.

- [ ] **Step 5: Marts pre-merge checklist**
      (`src/dbt/kipptaf/models/marts/CLAUDE.md`). Scan the added mart lines for
      diamond paths and rubric issues. The new columns hold no keys and no
      source-system names.

- [ ] **Step 6: Push and open the PR.** Push the branch. Open the PR against
      `main` from the template. Include `Refs #6192`; the linked branch closes
      #6145 on merge. Say plainly that Cube changes follow in a separate PR.
      Record 3 things: the Miami crosswalk choice (`int_powerschool__ada`,
      matched by `studentid`, every archived bucket student maps); middle-school
      `Algebra I` mapped to Math; and the 2 trailing-space Illuminate subjects
      left null, as in the dashboards. Check the PR's returned title and body.
      Offer to watch CI and answer `claude-review`.
