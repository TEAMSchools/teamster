# AP Dashboard Exam-Only Scores Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `rpt_tableau__ap_assessment_dashboard` so a student's AP exam
score is no longer silently dropped when they have no matching AP course
enrollment (issue [#4391](https://github.com/TEAMSchools/teamster/issues/4391)).

**Architecture:** Restructure the model's join chain around a new `subjects`
bridge CTE that unions AP subject codes from course enrollments and exam scores
independently, so the exam-score join no longer chains through the
course-enrollment join. Add a `subject_code` grain column, a third
`test_subject_area` state (`'Took AP exam, not enrolled in course.'`), and an
`ap_course_name` fallback to the exam's own crosswalk-resolved name.

**Tech Stack:** dbt (BigQuery), `kipptaf` project, dbt unit tests (dict-format
fixtures), BigQuery MCP for manual verification queries.

## Global Constraints

- Full design and validated queries:
  `docs/superpowers/specs/2026-07-14-ap-dashboard-exam-only-scores-design.md`.
- Never write student names, DOB, or other PII to a committed file, PR, or issue
  comment — chat/terminal output only (repo `CLAUDE.md` PII policy).
- All SQL follows `.trunk/config/.sqlfluff` (BigQuery dialect, trailing commas,
  single-quoted strings, 88-char lines). Run
  `/workspaces/teamster/.trunk/tools/trunk check --force <file>` from inside the
  branch checkout before pushing — the pre-commit hook only runs `fmt`, not the
  sqlfluff/yamllint checks that fire at pre-push/CI.
- `given`/`expect` dict scalars in dbt unit tests are normally UNQUOTED per repo
  convention, **except** a scalar containing a literal comma (e.g.
  `"Smith, Jane"`, `"Took course, but not AP exam."`) — inside a YAML flow
  mapping (`{ ... }`), an unquoted comma is parsed as a field separator, not as
  part of the string, and silently produces a bogus extra key. Quote only those
  values.
- `dbt` invocations: always `uv run`, never bare `python`/`dbt`. Use
  `DBT_PROFILES_DIR=/workspaces/teamster/.dbt` and
  `--project-dir /workspaces/teamster/src/dbt/kipptaf` on every call from the
  main repo (or the worktree-equivalent absolute paths per repo `CLAUDE.md` if
  executing from a worktree).
- Only one other file in the repo references this model:
  `src/dbt/kipptaf/models/exposures/tableau.yml` (the Tableau exposure
  definition). No downstream dbt model `ref()`s it — verified via
  `grep -rl "rpt_tableau__ap_assessment_dashboard" src/dbt`. No exposure edit is
  needed; this fix is self-contained to the one model + its properties file.
- Out of scope, do not touch: the `int_collegeboard__ap_unpivot` dedup bug
  (collapses multiple unresolved-crosswalk students via `dbt_utils.deduplicate`
  on a shared NULL `powerschool_student_number` — not tracked yet) and the
  PowerSchool AP-course-tagging gap tracked in #4390 (a data problem, not a
  join-structure problem). Also out of scope: how multiple exam attempts for the
  same subject are deduplicated (`int_assessments__ap_assessments.rn_highest` is
  not filtered on here, same as pre-fix behavior).

---

### Task 1: Add failing unit tests for the exam-only fix

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__ap_assessment_dashboard.yml:150`
  (append `unit_tests:` block at end of file; nothing else in the file changes
  in this task)

**Interfaces:**

- Consumes: the model's current (pre-fix) column set — `academic_year`,
  `student_number`, `ap_course_subject`, `test_name`, `test_subject`,
  `exam_score`, `data_source`, `ps_ap_course_subject_code`, `ap_course_name`,
  `course_name`, `test_subject_area`, `expected_scope`, `expected_test_type`.
- Produces: 5 unit tests that reference a `subject_code` output column the model
  does not yet have — these MUST fail until Task 2 adds it. Task 2 depends on
  these exact test names and fixture data existing:
  `test_course_enrollment_no_exam`, `test_course_enrollment_and_matching_exam`,
  `test_exam_only_no_course_enrollment`, `test_no_course_no_exam`,
  `test_two_exam_only_subjects_produce_two_distinct_rows`.

- [ ] **Step 1: Append the unit tests block**

Append this block to the end of
`src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__ap_assessment_dashboard.yml`
(the file currently ends after the `expected_test_type` column's `description:`
— add a blank line, then this):

```yaml
unit_tests:
  - name: test_course_enrollment_no_exam
    description: >-
      A student enrolled in an AP course who did not take the exam shows 'Took
      course, but not AP exam.' and resolves ap_course_name from the course-side
      crosswalk. Regression check: this branch existed before the fix and must
      keep working.
    model: rpt_tableau__ap_assessment_dashboard
    given:
      - input: ref('int_extracts__student_enrollments')
        rows:
          - {
              studentid: 101,
              student_number: 1001,
              academic_year: 2024,
              _dbt_source_relation: kippnewark_powerschool.stg_powerschool__students,
              rn_year: 1,
              school_level: HS,
              entrydate: 2024-08-01,
              exitdate: 2025-06-15,
              iep_status: No IEP,
            }
      - input: ref('base_powerschool__course_enrollments')
        rows:
          - {
              cc_studentid: 101,
              cc_academic_year: 2024,
              _dbt_source_relation: kippnewark_powerschool.stg_powerschool__cc,
              ap_course_subject: ENGLANG,
              is_dropped_section: false,
              rn_course_number_year: 1,
              courses_course_name: AP English Language,
              cc_dateenrolled: 2024-09-01,
              cc_dateleft: 2025-06-15,
              sections_external_expression: P3,
              teacher_lastfirst: "Smith, Jane",
            }
      - input: ref('stg_google_sheets__collegeboard__ap_course_crosswalk')
        rows:
          - {
              PS_AP_Course_Subject_Code: ENGLANG,
              AP_Course_Name: AP English Language and Composition,
              Data_Source: CB File,
            }
      - input: ref('int_assessments__ap_assessments')
        rows: []
    expect:
      rows:
        - {
            subject_code: ENGLANG,
            course_name: AP English Language,
            ap_course_name: AP English Language and Composition,
            test_subject_area: "Took course, but not AP exam.",
            expected_scope: AP,
            expected_test_type: Official,
          }

  - name: test_course_enrollment_and_matching_exam
    description: >-
      A student enrolled in an AP course who also has a matching exam score
      shows the exam's course name as test_subject_area. Regression check for
      the pre-existing matched case.
    model: rpt_tableau__ap_assessment_dashboard
    given:
      - input: ref('int_extracts__student_enrollments')
        rows:
          - {
              studentid: 102,
              student_number: 1002,
              academic_year: 2024,
              _dbt_source_relation: kippnewark_powerschool.stg_powerschool__students,
              rn_year: 1,
              school_level: HS,
              entrydate: 2024-08-01,
              exitdate: 2025-06-15,
              iep_status: No IEP,
            }
      - input: ref('base_powerschool__course_enrollments')
        rows:
          - {
              cc_studentid: 102,
              cc_academic_year: 2024,
              _dbt_source_relation: kippnewark_powerschool.stg_powerschool__cc,
              ap_course_subject: BIOLOGY,
              is_dropped_section: false,
              rn_course_number_year: 1,
              courses_course_name: AP Biology,
              cc_dateenrolled: 2024-09-01,
              cc_dateleft: 2025-06-15,
              sections_external_expression: P4,
              teacher_lastfirst: "Doe, John",
            }
      - input: ref('stg_google_sheets__collegeboard__ap_course_crosswalk')
        rows:
          - {
              PS_AP_Course_Subject_Code: BIOLOGY,
              AP_Course_Name: AP Biology,
              Data_Source: CB File,
            }
      - input: ref('int_assessments__ap_assessments')
        rows:
          - {
              academic_year: 2024,
              powerschool_student_number: 1002,
              test_name: AP Biology,
              test_subject: Biology,
              exam_score: 4,
              ps_ap_course_subject_code: BIOLOGY,
              ap_course_name: AP Biology,
              data_source: CB File,
            }
    expect:
      rows:
        - {
            subject_code: BIOLOGY,
            course_name: AP Biology,
            ap_course_name: AP Biology,
            test_subject_area: AP Biology,
            expected_scope: AP,
            expected_test_type: Official,
          }

  - name: test_exam_only_no_course_enrollment
    description: >-
      Fix for #4391: a student with an AP exam score but no matching AP course
      enrollment now surfaces as its own row with 'Took AP exam, not enrolled in
      course.' instead of disappearing. ap_course_name falls back to the exam's
      own crosswalk-resolved name since there is no course-side match.
    model: rpt_tableau__ap_assessment_dashboard
    given:
      - input: ref('int_extracts__student_enrollments')
        rows:
          - {
              studentid: 103,
              student_number: 1003,
              academic_year: 2024,
              _dbt_source_relation: kippnewark_powerschool.stg_powerschool__students,
              rn_year: 1,
              school_level: HS,
              entrydate: 2024-08-01,
              exitdate: 2025-06-15,
              iep_status: No IEP,
            }
      - input: ref('base_powerschool__course_enrollments')
        rows: []
      - input: ref('stg_google_sheets__collegeboard__ap_course_crosswalk')
        rows: []
      - input: ref('int_assessments__ap_assessments')
        rows:
          - {
              academic_year: 2024,
              powerschool_student_number: 1003,
              test_name: AP Chemistry,
              test_subject: Chemistry,
              exam_score: 3,
              ps_ap_course_subject_code: CHEM,
              ap_course_name: AP Chemistry,
              data_source: CB File,
            }
    expect:
      rows:
        - {
            subject_code: CHEM,
            ap_course_subject: null,
            course_name: Not an AP course,
            ap_course_name: AP Chemistry,
            test_subject_area: "Took AP exam, not enrolled in course.",
            expected_scope: Not applicable,
            expected_test_type: Not applicable,
          }

  - name: test_no_course_no_exam
    description: >-
      A non-participating HS student (no AP course, no AP exam) still gets
      exactly one row, unchanged from pre-fix behavior.
    model: rpt_tableau__ap_assessment_dashboard
    given:
      - input: ref('int_extracts__student_enrollments')
        rows:
          - {
              studentid: 104,
              student_number: 1004,
              academic_year: 2024,
              _dbt_source_relation: kippnewark_powerschool.stg_powerschool__students,
              rn_year: 1,
              school_level: HS,
              entrydate: 2024-08-01,
              exitdate: 2025-06-15,
              iep_status: No IEP,
            }
      - input: ref('base_powerschool__course_enrollments')
        rows: []
      - input: ref('stg_google_sheets__collegeboard__ap_course_crosswalk')
        rows: []
      - input: ref('int_assessments__ap_assessments')
        rows: []
    expect:
      rows:
        - {
            subject_code: null,
            course_name: Not an AP course,
            ap_course_name: Not an AP course,
            test_subject_area: Not applicable,
            expected_scope: Not applicable,
            expected_test_type: Not applicable,
          }

  - name: test_two_exam_only_subjects_produce_two_distinct_rows
    description: >-
      A student with exam scores in two different subjects and no course
      enrollment in either gets two distinct rows keyed by subject_code, proving
      the new grain key prevents the collision that ap_course_subject (always
      NULL for both rows) would cause.
    model: rpt_tableau__ap_assessment_dashboard
    given:
      - input: ref('int_extracts__student_enrollments')
        rows:
          - {
              studentid: 105,
              student_number: 1005,
              academic_year: 2024,
              _dbt_source_relation: kippnewark_powerschool.stg_powerschool__students,
              rn_year: 1,
              school_level: HS,
              entrydate: 2024-08-01,
              exitdate: 2025-06-15,
              iep_status: No IEP,
            }
      - input: ref('base_powerschool__course_enrollments')
        rows: []
      - input: ref('stg_google_sheets__collegeboard__ap_course_crosswalk')
        rows: []
      - input: ref('int_assessments__ap_assessments')
        rows:
          - {
              academic_year: 2024,
              powerschool_student_number: 1005,
              test_name: AP Chemistry,
              test_subject: Chemistry,
              exam_score: 3,
              ps_ap_course_subject_code: CHEM,
              ap_course_name: AP Chemistry,
              data_source: CB File,
            }
          - {
              academic_year: 2024,
              powerschool_student_number: 1005,
              test_name: AP Physics 1,
              test_subject: Physics 1,
              exam_score: 5,
              ps_ap_course_subject_code: PHYS1,
              ap_course_name: AP Physics 1,
              data_source: CB File,
            }
    expect:
      rows:
        - {
            subject_code: CHEM,
            test_subject_area: "Took AP exam, not enrolled in course.",
          }
        - {
            subject_code: PHYS1,
            test_subject_area: "Took AP exam, not enrolled in course.",
          }
```

- [ ] **Step 2: Run the unit tests and confirm they fail RED**

Run:

```bash
DBT_PROFILES_DIR=/workspaces/teamster/.dbt uv run dbt test \
  --select test_type:unit,rpt_tableau__ap_assessment_dashboard \
  --target dev --defer --state target/prod \
  --project-dir /workspaces/teamster/src/dbt/kipptaf
```

Expected: `Done. PASS=0 WARN=0 ERROR=5 SKIP=0 NO-OP=0 TOTAL=5`, with each of the
5 failures showing:

```text
Compilation Error in unit_test <test_name> (models/extracts/tableau/properties/rpt_tableau__ap_assessment_dashboard.yml)
  Invalid column name: 'subject_code' in unit test fixture for expected output.
  Accepted columns for expected output are: ['academic_year', ... 'expected_test_type']
```

This confirms the tests correctly detect that `subject_code` doesn't exist on
the model yet — the RED state driving Task 2.

- [ ] **Step 3: Commit**

```bash
git add src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__ap_assessment_dashboard.yml
git commit -m "test: add failing unit tests for AP dashboard exam-only scores (#4391)"
```

---

### Task 2: Restructure the model and make the tests pass

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__ap_assessment_dashboard.sql`
  (full rewrite)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__ap_assessment_dashboard.yml:1-149`
  (model description, uniqueness test key, new `subject_code` column, updated
  `ap_course_name`/`test_subject_area` descriptions — the `unit_tests:` block
  from Task 1 is untouched)

**Interfaces:**

- Consumes: the 5 unit tests from Task 1 (must all pass after this task).
  Upstream refs unchanged: `int_extracts__student_enrollments`,
  `base_powerschool__course_enrollments`,
  `stg_google_sheets__collegeboard__ap_course_crosswalk`,
  `int_assessments__ap_assessments`.
- Produces: `subject_code` (STRING) — the bridged grain key other tasks/future
  consumers would join on. `ap_course_subject` keeps its exact prior meaning
  (course-enrollment-only, nullable).

- [ ] **Step 1: Replace the model SQL**

Replace the full contents of
`src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__ap_assessment_dashboard.sql`
with:

```sql
with
    course_enrollments as (
        select
            _dbt_source_relation,
            cc_studentid,
            cc_academic_year,
            ap_course_subject,
            cc_dateenrolled,
            cc_dateleft,
            sections_external_expression,
            teacher_lastfirst,
            courses_course_name,
        from {{ ref("base_powerschool__course_enrollments") }}
        where rn_course_number_year = 1 and ap_course_subject is not null and not is_dropped_section
    ),

    ap_assessments as (
        select
            academic_year,
            powerschool_student_number,
            test_name,
            test_subject,
            exam_score,
            irregularity_code_1,
            irregularity_code_2,
            data_source,
            ps_ap_course_subject_code,
            ap_course_name,
        from {{ ref("int_assessments__ap_assessments") }}
        where test_subject != 'Calculus BC: AB Subscore'
    ),

    subjects as (
        select distinct
            e.studentid,
            e.student_number,
            e.academic_year,
            e._dbt_source_relation,
            c.ap_course_subject as subject_code,
        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            course_enrollments as c
            on e.studentid = c.cc_studentid
            and e.academic_year = c.cc_academic_year
            and {{ union_dataset_join_clause(left_alias="e", right_alias="c") }}

        union distinct

        select distinct
            e.studentid,
            e.student_number,
            e.academic_year,
            e._dbt_source_relation,
            ap.ps_ap_course_subject_code as subject_code,
        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            ap_assessments as ap
            on e.academic_year = ap.academic_year
            and e.student_number = ap.powerschool_student_number
    )

select
    e.academic_year,
    e.academic_year_display,
    e.region,
    e.schoolid,
    e.school,
    e.student_number,
    e.student_name,
    e.grade_level,
    e.enroll_status,
    e.entrydate,
    e.exitdate,
    e.cohort,
    e.advisory,
    e.is_enrolled_recent,
    e.is_enrolled_y1,
    e.is_504 as c_504_status,
    e.lep_status,
    e.gifted_and_talented,
    e.salesforce_id as contact_id,
    e.ktc_cohort,
    e.graduation_year,

    sub.subject_code,

    s.cc_dateenrolled as ap_date_enrolled,
    s.cc_dateleft as ap_date_left,
    s.sections_external_expression as ap_course_section,
    s.teacher_lastfirst as ap_teacher_name,
    s.ap_course_subject,

    a.test_name,
    a.test_subject,
    a.exam_score,
    a.irregularity_code_1,
    a.irregularity_code_2,
    a.data_source,
    a.ps_ap_course_subject_code,

    coalesce(x.ap_course_name, a.ap_course_name, 'Not an AP course') as ap_course_name,

    coalesce(s.courses_course_name, 'Not an AP course') as course_name,

    case
        when s.courses_course_name is null and a.test_name is null
        then 'Not applicable'
        when s.courses_course_name is not null and a.test_name is null
        then 'Took course, but not AP exam.'
        when s.courses_course_name is null and a.test_name is not null
        then 'Took AP exam, not enrolled in course.'
        else a.ap_course_name
    end as test_subject_area,

    if(e.iep_status = 'No IEP', 0, 1) as sped,

    if(s.courses_course_name is null, 'Not applicable', 'AP') as expected_scope,

    if(
        s.courses_course_name is null, 'Not applicable', 'Official'
    ) as expected_test_type,

from {{ ref("int_extracts__student_enrollments") }} as e
left join
    subjects as sub
    on e.studentid = sub.studentid
    and e.academic_year = sub.academic_year
    and {{ union_dataset_join_clause(left_alias="e", right_alias="sub") }}
left join
    course_enrollments as s
    on sub.studentid = s.cc_studentid
    and sub.academic_year = s.cc_academic_year
    and sub.subject_code = s.ap_course_subject
    and {{ union_dataset_join_clause(left_alias="sub", right_alias="s") }}
left join
    ap_assessments as a
    on sub.student_number = a.powerschool_student_number
    and sub.academic_year = a.academic_year
    and sub.subject_code = a.ps_ap_course_subject_code
left join
    {{ ref("stg_google_sheets__collegeboard__ap_course_crosswalk") }} as x
    on sub.subject_code = x.ps_ap_course_subject_code
    and x.data_source = 'CB File'
where
    e.rn_year = 1
    and e.school_level = 'HS'
    and date(e.academic_year + 1, 05, 01) between e.entrydate and e.exitdate
```

- [ ] **Step 2: Update the properties file**

In
`src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__ap_assessment_dashboard.yml`,
make these four edits (the `unit_tests:` block from Task 1 stays as-is at the
end of the file):

1. Model `description:` (currently ends "...who did not take the exam.") —
   replace with:

   ```yaml
   description: >
     AP assessment scores joined to student enrollment and course schedules for
     Tableau reporting. One row per student per AP course subject, including
     students enrolled in AP courses who did not take the exam and students who
     took an exam with no matching AP course enrollment.
   ```

2. `data_tests.dbt_utils.unique_combination_of_columns.arguments.combination_of_columns`
   — change the third entry from `ap_course_subject` to `subject_code`:

   ```yaml
   data_tests:
     - dbt_utils.unique_combination_of_columns:
         arguments:
           combination_of_columns:
             - academic_year
             - student_number
             - subject_code
   ```

3. Insert a new column entry immediately after `graduation_year` and before
   `ap_date_enrolled`:

   ```yaml
   - name: subject_code
     data_type: string
     description: >
       AP subject code bridging course enrollment and exam records for the
       report grain — the course-enrollment subject code when the student is
       enrolled in an AP course, otherwise the exam's own College Board subject
       code. NULL only when the student has neither.
   ```

4. Replace the `ap_course_name` and `test_subject_area` column `description:`
   fields:

   ```yaml
   - name: ap_course_name
     data_type: string
     description: >
       AP course name from the College Board crosswalk when the student has an
       AP course enrollment; otherwise the exam's own crosswalk-resolved name
       when the student took the exam with no matching course; 'Not an AP
       course' if neither resolves.
   ```

   ```yaml
   - name: test_subject_area
     data_type: string
     description: >
       Derived field indicating exam relationship to course: 'Not applicable' if
       no AP course and no exam, 'Took course, but not AP exam.' if enrolled but
       did not test, 'Took AP exam, not enrolled in course.' if tested with no
       matching course enrollment, otherwise the College Board AP course name.
   ```

- [ ] **Step 3: Run the unit tests and confirm GREEN**

Run the same command as Task 1 Step 2:

```bash
DBT_PROFILES_DIR=/workspaces/teamster/.dbt uv run dbt test \
  --select test_type:unit,rpt_tableau__ap_assessment_dashboard \
  --target dev --defer --state target/prod \
  --project-dir /workspaces/teamster/src/dbt/kipptaf
```

Expected: `Done. PASS=5 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=5`.

- [ ] **Step 4: Full dev build and contract/uniqueness check**

Run:

```bash
DBT_PROFILES_DIR=/workspaces/teamster/.dbt uv run dbt build \
  --select rpt_tableau__ap_assessment_dashboard \
  --target dev --defer --state target/prod \
  --project-dir /workspaces/teamster/src/dbt/kipptaf
```

Expected: the 5 unit tests PASS, the view builds (`CREATE VIEW (0 processed)`),
and the uniqueness test reports `WARN 3` (not an ERROR) —
`Got 3 results, configured to warn if != 0`. This WARN is **expected and
pre-existing**, not a regression: it is the same 3-row duplicate (academic_year
2021, `subject_code = '4'` / Calculus BC, three Newark students, each with two
PowerSchool course-enrollment rows for distinct `course_number`s both tagged
`ap_course_subject = '4'` — a main section plus a companion "Recitation"
section) that already exists in prod today keyed on
`(academic_year, student_number, ap_course_subject)`. Confirm this by running,
via BigQuery MCP:

```sql
select academic_year, student_number, ap_course_subject, count(*) as n
from `teamster-332318`.kipptaf_tableau.rpt_tableau__ap_assessment_dashboard
group by academic_year, student_number, ap_course_subject
having count(*) > 1
```

This should return the same 3 rows. If it returns different rows or a different
count, stop and investigate before proceeding — that would mean the fix
introduced a new duplication source, not carried forward an old one. Do not add
a defensive dedupe for this — it matches the repo's standing convention for the
similar `base_powerschool__course_enrollments` double-write issue (#3900/#3915):
downgrade/track, don't dedupe. No action needed here since the test already
defaults to WARN (no severity override in this model's yml).

- [ ] **Step 5: Format and lint**

```bash
/workspaces/teamster/.trunk/tools/trunk fmt \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__ap_assessment_dashboard.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__ap_assessment_dashboard.yml
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__ap_assessment_dashboard.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__ap_assessment_dashboard.yml
```

Expected: `✔ No issues` after `fmt` resolves any formatting-only diffs. Fix
anything `check` reports before continuing.

- [ ] **Step 6: Commit**

```bash
git add src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__ap_assessment_dashboard.sql
git add src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__ap_assessment_dashboard.yml
git commit -m "fix: surface AP exam scores with no matching course enrollment (#4391)"
```

---

### Task 3: Verify against prod — row diff, reconciliation, and known cases

**Files:** none — this task is read-only verification via the BigQuery MCP
(`mcp__bigquery__execute_sql`) against the dev build from Task 2 and the prod
table. Nothing here is committed to git; PII-adjacent results (student names)
stay in chat only per repo policy.

**Interfaces:**

- Consumes: the dev-schema table materialized in Task 2 Step 4
  (`zz_<your-github-username>_kipptaf_tableau.rpt_tableau__ap_assessment_dashboard`
  — find the exact schema name from the Task 2 Step 4 build log, or query
  `INFORMATION_SCHEMA.SCHEMATA` per repo `CLAUDE.md` "Local dev schema naming"
  guidance) and the prod table
  `kipptaf_tableau.rpt_tableau__ap_assessment_dashboard`.
- Produces: a chat-only summary (added/deleted counts by `test_subject_area`,
  reconciliation result, spot-check confirmation) — no file output.

- [ ] **Step 1: Run the null-safe row diff**

Run via BigQuery MCP (substitute `<dev_schema>` with your actual dev schema from
Task 2 Step 4):

```sql
with
    prod as (
        select
            academic_year, student_number,
            ifnull(ap_course_subject, '__none__') as subject_code_key,
            test_subject_area
        from `teamster-332318`.kipptaf_tableau.rpt_tableau__ap_assessment_dashboard
    ),
    dev as (
        select
            academic_year, student_number,
            ifnull(subject_code, '__none__') as subject_code_key,
            test_subject_area
        from `teamster-332318`.<dev_schema>.rpt_tableau__ap_assessment_dashboard
    ),
    added as (
        select dev.*
        from dev
        left join prod
            on dev.academic_year = prod.academic_year
            and dev.student_number = prod.student_number
            and dev.subject_code_key = prod.subject_code_key
        where prod.student_number is null
    ),
    deleted as (
        select prod.*
        from prod
        left join dev
            on prod.academic_year = dev.academic_year
            and prod.student_number = dev.student_number
            and prod.subject_code_key = dev.subject_code_key
        where dev.student_number is null
    )
select 'added' as change_type, test_subject_area, count(*) as row_count
from added
group by test_subject_area
union all
select 'deleted' as change_type, test_subject_area, count(*) as row_count
from deleted
group by test_subject_area
order by change_type
```

Expected shape (validated 2026-07-14 against then-current prod data; your exact
counts will differ since underlying enrollment/exam data changes daily — that's
fine, only the _shape_ matters):

- One `added` row grouped under
  `test_subject_area = 'Took AP exam, not enrolled in course.'` — nonzero,
  spanning potentially many historical academic years (this bug predates 2018
  and isn't year-scoped, so the fix surfaces more than just the 3 cases cited in
  #4391).
- If `added` shows ANY other `test_subject_area` value, stop — that's unexpected
  and needs investigation before merging.
- One or more `deleted` rows, likely under
  `test_subject_area = 'Not applicable'`.

- [ ] **Step 2: Run the reconciliation check on the `deleted` bucket**

A `deleted` row is not automatically a regression — a student who was a total
non-participant (`'Not applicable'` placeholder row) and turns out to have an
exam-only score gets that placeholder _replaced_ by a real subject row, which
looks like one delete + one add for the same student/year, not a net loss. Run
(reusing the `added`/`deleted` CTEs from Step 1):

```sql
select
    count(*) as deleted_rows,
    countif(a.student_number is not null) as accounted_for_by_an_added_row,
    countif(a.student_number is null) as true_regressions
from deleted as d
left join (select distinct academic_year, student_number from added) as a
    on d.academic_year = a.academic_year and d.student_number = a.student_number
```

Expected: `true_regressions = 0` (validated 0/119 on 2026-07-14 prod data). If
`true_regressions > 0`, stop and investigate those specific
`(academic_year, student_number)` pairs before merging — that means the
restructured joins lost a row with no offsetting replacement.

- [ ] **Step 3: Spot-check the 3 originally-reported students (chat only)**

Using the 3 student identities from #4391 (kept local — do not paste them into
any committed file, issue comment, or PR description), query the dev table and
confirm each now shows
`test_subject_area = 'Took AP exam, not enrolled in course.'` with a populated
`ap_course_name`. Report the confirmation in chat as "3/3 confirmed", not by
pasting the student rows into any persisted output.

- [ ] **Step 4: Summarize findings in chat**

Report to the user: total `added` count and its single `test_subject_area`
bucket, total `deleted` count, `true_regressions` count (must be 0 to proceed),
and the 3/3 spot-check confirmation. This is the deliverable for this task — no
commit.

---

### Task 4: Finish the branch

**Files:** none (repo-level checks only).

**Interfaces:**

- Consumes: the committed changes from Tasks 1–2 and the verification findings
  from Task 3.
- Produces: a PR-ready branch.

- [ ] **Step 1: Full project sanity check**

```bash
DBT_PROFILES_DIR=/workspaces/teamster/.dbt uv run dbt parse --target prod \
  --project-dir /workspaces/teamster/src/dbt/kipptaf
```

Expected: parses cleanly with no errors (confirms nothing else in the 750-model
kipptaf project broke from this change — no warehouse write, safe to run without
prod-deploy approval per repo `CLAUDE.md`).

- [ ] **Step 2: Review the full diff**

```bash
git log --oneline main..HEAD
git diff main..HEAD --stat
```

Expected: 2 commits (Task 1's test commit, Task 2's fix commit), touching only
the model `.sql` and its `properties.yml`.

- [ ] **Step 3: Hand off**

Report the Task 3 verification summary to the user and invoke
`superpowers:finishing-a-development-branch` to decide on PR vs. further changes
— do not push or open a PR without the user's go-ahead per repo `CLAUDE.md`
conventions (dbt Cloud CI state check before pushing, PR template usage, etc.).
