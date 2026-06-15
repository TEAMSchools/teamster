# Assessment + Teacher Roster Google Sheets Extracts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship two kipptaf Google Sheets extracts — a PII-stripped assessment
roster (student/test/round grain) and a teacher roster (teacher/year grain) —
plus the assessment anon-id crosswalk that backs the first.

**Architecture:** Model 1 uses a union intermediate
(`int_assessments__roster_union`) that normalizes five assessment sources, a
private anon-id crosswalk (`int_assessments__student_anon_crosswalk`), and a
thin reporting view (`rpt_gsheets__assessment_roster`) that joins demographics +
course enrollment and swaps `student_number` for the anon id. Model 2 is a
single reporting view (`rpt_gsheets__teacher_roster`) joining staff roster +
current-year performance + experience.

**Tech Stack:** dbt (BigQuery dialect), kipptaf project. Validation via
`uv run dbt build`. SQL must follow `.trunk/config/.sqlfluff` (trailing commas,
single quotes, 88-char lines, BigQuery reserved words backticked).

**Design spec:**
`docs/superpowers/specs/2026-06-15-assessment-roster-extract-design.md` (issue
[#4191](https://github.com/TEAMSchools/teamster/issues/4191)).

---

## Conventions for every task

- All commands run from the repo root `/workspaces/teamster` on branch
  `anthonygwalters/feat/claude-assessment-roster-extract`.
- **Build/test command template** (parents may not exist in dev, so defer to the
  prod manifest):

  ```bash
  uv run dbt build --select <model> \
      --project-dir src/dbt/kipptaf \
      --defer --state target/prod
  ```

  `--state` is relative to `--project-dir`, i.e. `src/dbt/kipptaf/target/prod`.
  If the manifest is stale, refresh it first:

  ```bash
  uv run dbt parse --target prod \
      --project-dir src/dbt/kipptaf --target-path target/prod
  ```

- **Lint before each commit** (run from repo root):

  ```bash
  /workspaces/teamster/.trunk/tools/trunk check --force <changed files>
  ```

- Intermediate models need a uniqueness test (no contract). `rpt_` models need
  `contract: enforced: true` (inherited from `extracts/`) — every column needs a
  `data_type` in YAML, and a uniqueness test.
- `prod`-target builds are blocked for Claude — all builds here use the default
  (dev) target with `--defer`. Hand any `--target prod` run to the user.

---

## Task 1: Anon-id crosswalk — `int_assessments__student_anon_crosswalk`

**Files:**

- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__student_anon_crosswalk.sql`
- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__student_anon_crosswalk.yml`

- [ ] **Step 1: Write the model SQL**

The population is every `student_number` present in the demographics model
within the two-year window, so the crosswalk covers exactly the students model 1
can emit.

```sql
with
    students as (
        select student_number,
        from {{ ref("int_extracts__student_enrollments_subjects") }}
        where
            academic_year
            in ({{ var("current_academic_year") }}, {{ var("current_academic_year") }} - 1)
    )

select distinct
    student_number,
    {{ dbt_utils.generate_surrogate_key(["student_number"]) }} as student_anon_id,
from students
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: int_assessments__student_anon_crosswalk
    description: >
      Internal-only decode table mapping student_number to its stable anonymized
      id (student_anon_id) for the assessment roster extract. Never exposed to
      Google Sheets; query it in BigQuery to decode a sheet value back to
      student_number. One row per student_number in the two-year assessment
      window.
    columns:
      - name: student_number
        description: PowerSchool student number (the value to decode back to).
        data_tests:
          - unique
          - not_null
      - name: student_anon_id
        description: >
          Stable surrogate hash of student_number; the value that appears in the
          assessment roster sheet in place of student_number.
        data_tests:
          - not_null
```

- [ ] **Step 3: Build and test**

```bash
uv run dbt build --select int_assessments__student_anon_crosswalk \
    --project-dir src/dbt/kipptaf --defer --state target/prod
```

Expected: model builds; `unique` + `not_null` tests pass.

- [ ] **Step 4: Lint**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
    src/dbt/kipptaf/models/assessments/intermediate/int_assessments__student_anon_crosswalk.sql \
    src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__student_anon_crosswalk.yml
```

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/assessments/intermediate/int_assessments__student_anon_crosswalk.sql \
        src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__student_anon_crosswalk.yml
git commit -m "feat(dbt): add int_assessments__student_anon_crosswalk (#4191)"
```

---

## Task 2: Verify source columns for the union

Before writing the union, confirm the exact source column names the spec relies
on. This prevents a build-fail loop on the large model.

**Files:** none (inspection only).

- [ ] **Step 1: Read each source model's properties YAML** and confirm the
      columns named in the spec mapping table exist with these names:

  - `int_iready__diagnostic_results`: `student_id`, `academic_year_int`,
    `subject`, `test_round`, `overall_scale_score`, `is_proficient`,
    `overall_relative_placement`, `overall_relative_placement_int`.
  - `int_fldoe__all_assessments`: `student_number`, `academic_year`,
    `illuminate_subject`, `administration_window`, `scale_score`,
    `is_proficient`, `achievement_level`, `performance_level`.
  - `int_amplify__all_assessments`: `student_number`, `academic_year`,
    `assessment_type`, `measure_standard`, `period`, `measure_standard_score`,
    `aggregated_measure_standard_level`, `measure_standard_level`,
    `measure_standard_level_int`.
  - `int_pearson__all_assessments`: `localstudentidentifier`, `academic_year`,
    `illuminate_subject`, `assessment_name`, `admin`, `testscalescore`,
    `is_proficient`, `testperformancelevel_text`, `testperformancelevel`.
  - `int_assessments__response_rollup`: `powerschool_student_number`,
    `academic_year`, `discipline`, `module_type`, `module_code`,
    `response_type`, `assessment_id`, `title`, `percent_correct`, `is_mastery`,
    `performance_band_label`, `performance_band_label_number`.

  Read with:

  ```bash
  rg -n 'name:' src/dbt/kipptaf/models/iready/intermediate/properties/int_iready__diagnostic_results.yml
  ```

  (repeat per model/properties path).

- [ ] **Step 2: Confirm the NJSLA subject domain.** Query the distinct
      `illuminate_subject` values present for `assessment_name = 'NJSLA'` so the
      ELA/Math mapping is exhaustive and excludes science:

  ```sql
  select distinct illuminate_subject, subject
  from `teamster-332318`.kipptaf_pearson.int_pearson__all_assessments
  where assessment_name = 'NJSLA'
  ```

  Run via the BigQuery MCP. Record the mapping (e.g.
  `English Language Arts/Literacy` → ELA, `Mathematics`/`Algebra I`/`Geometry` →
  Math) for use in Step 1 of Task 3. If any non-ELA/Math subject appears, it is
  filtered out.

- [ ] **Step 3:** If any column name differs from the spec, note the correction
      inline in the Task 3 SQL below before writing it. No commit (inspection
      only).

---

## Task 3: Union intermediate — `int_assessments__roster_union`

**Files:**

- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__roster_union.sql`
- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__roster_union.yml`

- [ ] **Step 1: Write the model SQL.** One CTE per source normalized to the
      common schema, then `union all`. The window filter
      (`academic_year in (current, current-1)`) and `subject in ('ELA','Math')`
      are applied per source. `subject` is backticked (BigQuery-safe).

```sql
with
    iready as (
        select
            student_id as student_number,
            academic_year_int as academic_year,
            'i-Ready' as assessment_source,
            cast(null as string) as assessment_id,
            cast(null as string) as assessment_title,
            test_round as administration_round,
            overall_scale_score as scale_score,
            cast(null as numeric) as percent_correct,
            is_proficient,
            overall_relative_placement as performance_band_label,
            overall_relative_placement_int as performance_band_int,
            case
                when subject = 'Reading' then 'ELA' when subject = 'Math' then 'Math'
            end as `subject`,
        from {{ ref("int_iready__diagnostic_results") }}
        where
            subject in ('Reading', 'Math')
            and academic_year_int
            in ({{ var("current_academic_year") }}, {{ var("current_academic_year") }} - 1)
    ),

    fast as (
        select
            student_number,
            academic_year,
            'FAST' as assessment_source,
            cast(null as string) as assessment_id,
            cast(null as string) as assessment_title,
            administration_window as administration_round,
            scale_score,
            cast(null as numeric) as percent_correct,
            is_proficient,
            achievement_level as performance_band_label,
            performance_level as performance_band_int,
            case
                when illuminate_subject = 'Text Study'
                then 'ELA'
                when illuminate_subject = 'Mathematics'
                then 'Math'
            end as `subject`,
        from {{ ref("int_fldoe__all_assessments") }}
        where
            illuminate_subject in ('Text Study', 'Mathematics')
            and academic_year
            in ({{ var("current_academic_year") }}, {{ var("current_academic_year") }} - 1)
    ),

    dibels as (
        select
            student_number,
            academic_year,
            'DIBELS' as assessment_source,
            cast(null as string) as assessment_id,
            cast(null as string) as assessment_title,
            period as administration_round,
            measure_standard_score as scale_score,
            cast(null as numeric) as percent_correct,
            aggregated_measure_standard_level = 'At/Above' as is_proficient,
            measure_standard_level as performance_band_label,
            measure_standard_level_int as performance_band_int,
            'ELA' as `subject`,
        from {{ ref("int_amplify__all_assessments") }}
        where
            assessment_type = 'Benchmark'
            and measure_standard = 'Composite'
            and academic_year
            in ({{ var("current_academic_year") }}, {{ var("current_academic_year") }} - 1)
    ),

    njsla as (
        select
            localstudentidentifier as student_number,
            academic_year,
            'NJSLA' as assessment_source,
            cast(null as string) as assessment_id,
            cast(null as string) as assessment_title,
            admin as administration_round,
            testscalescore as scale_score,
            cast(null as numeric) as percent_correct,
            is_proficient,
            testperformancelevel_text as performance_band_label,
            cast(testperformancelevel as int) as performance_band_int,
            case
                when illuminate_subject = 'Text Study'
                then 'ELA'
                when illuminate_subject = 'Mathematics'
                then 'Math'
            end as `subject`,
        from {{ ref("int_pearson__all_assessments") }}
        where
            assessment_name = 'NJSLA'
            and illuminate_subject in ('Text Study', 'Mathematics')
            and academic_year = {{ var("current_academic_year") }} - 1
    ),

    internal as (
        select
            powerschool_student_number as student_number,
            academic_year,
            'Internal' as assessment_source,
            cast(assessment_id as string) as assessment_id,
            title as assessment_title,
            module_code as administration_round,
            cast(null as int) as scale_score,
            percent_correct,
            is_mastery as is_proficient,
            performance_band_label,
            cast(performance_band_label_number as int) as performance_band_int,
            discipline as `subject`,
        from {{ ref("int_assessments__response_rollup") }}
        where
            module_type in ('QA', 'MQQ', 'CRQ')
            and response_type = 'overall'
            and discipline in ('ELA', 'Math')
            and academic_year
            in ({{ var("current_academic_year") }}, {{ var("current_academic_year") }} - 1)
    ),

    unioned as (
        select *
        from iready
        union all
        select *
        from fast
        union all
        select *
        from dibels
        union all
        select *
        from njsla
        union all
        select *
        from internal
    )

select
    *,
    {{
        dbt_utils.generate_surrogate_key(
            [
                "student_number",
                "assessment_source",
                "subject",
                "administration_round",
                "coalesce(assessment_id, 'none')",
            ]
        )
    }} as surrogate_key,
from unioned
```

> Note on types: confirm `scale_score` and `performance_band_int` resolve to a
> single type across branches. If sources disagree (e.g. int vs float),
> standardize each branch with an explicit `cast(... as numeric)` /
> `cast(... as int)` so `union all` succeeds. Adjust the casts shown above to
> match the verified source types from Task 2.

- [ ] **Step 2: Write the properties YAML** (uniqueness on the grain, no
      contract — intermediate). Reuse the verified column meanings.

```yaml
models:
  - name: int_assessments__roster_union
    description: >
      Long-format union of five assessment sources (i-Ready, FAST, DIBELS,
      NJSLA, internal) normalized to one schema for the assessment roster
      extract. Scoped to ELA & Math, current + prior academic year. One row per
      student / assessment source / subject / administration round / assessment
      (assessment_id is null for benchmark and state sources, the Illuminate
      assessment id for internal assessments).
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_number
              - assessment_source
              - subject
              - administration_round
              - assessment_id
    columns:
      - name: surrogate_key
        description: Surrogate key over the row grain.
        data_tests:
          - unique
          - not_null
      - name: student_number
        description: PowerSchool student number.
        data_tests:
          - not_null
      - name: academic_year
        description: Academic year (start-year integer).
        data_tests:
          - not_null
      - name: assessment_source
        description: >
          Originating source: i-Ready, FAST, DIBELS, NJSLA, or Internal.
        data_tests:
          - not_null
          - accepted_values:
              arguments:
                values: [i-Ready, FAST, DIBELS, NJSLA, Internal]
      - name: subject
        description: Normalized subject — ELA or Math.
        quote: true
        data_tests:
          - not_null
          - accepted_values:
              arguments:
                values: [ELA, Math]
      - name: administration_round
        description: >
          Source-native administration window (BOY/MOY/EOY, PM1-PM3, Spring) or
          module_code for internal assessments.
      - name: assessment_id
        description: Illuminate assessment id (internal only; null otherwise).
      - name: assessment_title
        description: Assessment title (internal only; null otherwise).
      - name: scale_score
        description: Scale score (null for internal assessments).
      - name: percent_correct
        description: Percent correct (internal assessments only).
      - name: is_proficient
        description: >
          Proficiency/mastery boolean. DIBELS derived from
          aggregated_measure_standard_level = 'At/Above'.
      - name: performance_band_label
        description: Source-native performance band as a string label.
      - name: performance_band_int
        description: Source-native performance band as an integer.
```

- [ ] **Step 3: Build and test**

```bash
uv run dbt build --select int_assessments__roster_union \
    --project-dir src/dbt/kipptaf --defer --state target/prod
```

Expected: builds; uniqueness, `not_null`, and `accepted_values` tests pass. If
the uniqueness test fails, do NOT add a `qualify row_number()` dedupe — inspect
which source duplicates at the grain and fix the per-source filter (e.g. an
unexpected non-Composite DIBELS row, or a multi-subject NJSLA row).

- [ ] **Step 4: Lint**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
    src/dbt/kipptaf/models/assessments/intermediate/int_assessments__roster_union.sql \
    src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__roster_union.yml
```

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/assessments/intermediate/int_assessments__roster_union.sql \
        src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__roster_union.yml
git commit -m "feat(dbt): add int_assessments__roster_union (#4191)"
```

---

## Task 4: Assessment roster view — `rpt_gsheets__assessment_roster`

**Files:**

- Create:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__assessment_roster.sql`
- Create:
  `src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__assessment_roster.yml`

- [ ] **Step 1: Confirm the demographics + course-enrollment column names.**
      Read the properties YAMLs and confirm: in
      `int_extracts__student_enrollments_subjects` — `school_abbreviation`,
      `region`, `grade_level`, `iep_status`, `lep_status`, `status_504`; in
      `base_powerschool__course_enrollments` — `students_student_number`,
      `cc_academic_year`, `courses_credittype`, `rn_credittype_year`,
      `is_dropped_section`, `teachernumber`, `cc_course_number`,
      `cc_section_number`.

- [ ] **Step 2: Write the model SQL.** A course-enrollment CTE narrowed to one
      ENG/MATH row per student/year, then left-joined to the union by subject.
      Demographics scope the population to enrolled K-8. `student_number` is
      replaced by `student_anon_id` and dropped. Columns are enumerated (no
      `select *` in a contract-enforced `rpt_` final select).

```sql
with
    courses as (
        select
            students_student_number as student_number,
            cc_academic_year as academic_year,
            courses_credittype as credittype,
            teachernumber as teacher_powerschool_teacher_number,
            cc_course_number as course_number,
            cc_section_number as section_number,
        from {{ ref("base_powerschool__course_enrollments") }}
        where
            rn_credittype_year = 1
            and not is_dropped_section
            and courses_credittype in ('ENG', 'MATH')
    )

select
    cw.student_anon_id,

    ru.academic_year,
    ru.assessment_source,
    ru.`subject`,
    ru.administration_round,
    ru.assessment_title,
    ru.scale_score,
    ru.percent_correct,
    ru.is_proficient,
    ru.performance_band_label,
    ru.performance_band_int,

    se.region,
    se.school_abbreviation,
    se.grade_level,
    se.iep_status,
    se.status_504,

    c.teacher_powerschool_teacher_number,
    c.course_number,
    c.section_number,

    se.lep_status as ml_status,
from {{ ref("int_assessments__roster_union") }} as ru
inner join
    {{ ref("int_extracts__student_enrollments_subjects") }} as se
    on ru.student_number = se.student_number
    and ru.academic_year = se.academic_year
inner join
    {{ ref("int_assessments__student_anon_crosswalk") }} as cw
    on ru.student_number = cw.student_number
left join
    courses as c
    on ru.student_number = c.student_number
    and ru.academic_year = c.academic_year
    and case
        when ru.`subject` = 'ELA' then 'ENG' when ru.`subject` = 'Math' then 'MATH'
    end = c.credittype
where se.grade_level between 0 and 8
```

> The `se` join is `inner` to scope to enrolled K-8 students (population
> definition). If `int_extracts__student_enrollments_subjects` is multi-row per
> student/year (it cross-joins subjects), de-duplicate the demographics columns
> first in a CTE
> (`select distinct student_number, academic_year, region, school_abbreviation, grade_level, iep_status, lep_status, status_504`)
> to avoid fan-out — verify its grain in Step 1 and add the CTE if needed.

- [ ] **Step 3: Write the properties YAML** with `contract: enforced` columns
      and a uniqueness test on the row grain.

```yaml
models:
  - name: rpt_gsheets__assessment_roster
    description: >
      PII-stripped assessment roster for Google Sheets, student/test/round
      grain, K-8 ELA & Math, current + prior academic year. student_number is
      replaced by student_anon_id (decode via
      int_assessments__student_anon_crosswalk). One row per student / assessment
      source / subject / administration round / assessment.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_anon_id
              - assessment_source
              - subject
              - administration_round
              - assessment_title
    columns:
      - name: student_anon_id
        data_type: string
        description: Stable anonymized student id (decode via the crosswalk).
        data_tests:
          - not_null
      - name: academic_year
        data_type: int
        description: Academic year (start-year integer).
      - name: region
        data_type: string
        description: Student region.
      - name: school_abbreviation
        data_type: string
        description: School abbreviation.
      - name: grade_level
        data_type: int
        description: Grade level (0 = K through 8).
      - name: iep_status
        data_type: string
        description: IEP status.
      - name: ml_status
        data_type: string
        description: Multilingual-learner status (from lep_status).
      - name: status_504
        data_type: string
        description: 504 status.
      - name: assessment_source
        data_type: string
        description: i-Ready, FAST, DIBELS, NJSLA, or Internal.
      - name: subject
        data_type: string
        quote: true
        description: ELA or Math.
      - name: administration_round
        data_type: string
        description: Source-native window, or module_code for internal.
      - name: assessment_title
        data_type: string
        description: Assessment title (internal only).
      - name: teacher_powerschool_teacher_number
        data_type: string
        description: >
          PowerSchool teacher number for the matched ENG/MATH course (null when
          no match); join key to rpt_gsheets__teacher_roster.
      - name: course_number
        data_type: string
        description: Matched course number (null when no match).
      - name: section_number
        data_type: string
        description: Matched section number (null when no match).
      - name: scale_score
        data_type: int
        description: Scale score (null for internal).
      - name: percent_correct
        data_type: numeric
        description: Percent correct (internal only).
      - name: is_proficient
        data_type: boolean
        description: Proficiency/mastery boolean.
      - name: performance_band_label
        data_type: string
        description: Source-native band label.
      - name: performance_band_int
        data_type: int
        description: Source-native band integer.
```

> Confirm each `data_type` against the union's resolved output types (Task 3).
> `scale_score` / `performance_band_int` data_types must match the casts you
> settled on — `numeric` and `float64`/`int` are NOT interchangeable in a
> contract.

- [ ] **Step 4: Build and test**

```bash
uv run dbt build --select rpt_gsheets__assessment_roster \
    --project-dir src/dbt/kipptaf --defer --state target/prod
```

Expected: builds; contract enforced; uniqueness + `not_null` pass. A contract
type mismatch error names the offending column — fix the YAML `data_type` or the
SQL cast to agree.

- [ ] **Step 5: Lint**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
    src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__assessment_roster.sql \
    src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__assessment_roster.yml
```

- [ ] **Step 6: Commit**

```bash
git add src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__assessment_roster.sql \
        src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__assessment_roster.yml
git commit -m "feat(dbt): add rpt_gsheets__assessment_roster (#4191)"
```

---

## Task 5: Teacher roster view — `rpt_gsheets__teacher_roster`

**Files:**

- Create:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__teacher_roster.sql`
- Create:
  `src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__teacher_roster.yml`

- [ ] **Step 1: Confirm source columns.** In `int_people__staff_roster`:
      `employee_number`, `powerschool_teacher_number`, `job_title`,
      `level_of_education`. In `int_performance_management__overall_scores`:
      `employee_number`, `academic_year`, `final_score`, `final_tier`. In
      `int_people__years_experience`: `employee_number`, `academic_year`,
      `years_at_kipp_total`, `years_experience_total`, `years_teaching_total`.

- [ ] **Step 2: Write the model SQL.** Teachers only; perf + experience left
      joined on `employee_number` and the current academic year.

```sql
select
    sr.powerschool_teacher_number,
    sr.job_title,
    sr.level_of_education,

    os.final_score,
    os.final_tier,

    ye.years_at_kipp_total,
    ye.years_experience_total,
    ye.years_teaching_total,

    {{ var("current_academic_year") }} as academic_year,
from {{ ref("int_people__staff_roster") }} as sr
left join
    {{ ref("int_performance_management__overall_scores") }} as os
    on sr.employee_number = os.employee_number
    and os.academic_year = {{ var("current_academic_year") }}
left join
    {{ ref("int_people__years_experience") }} as ye
    on sr.employee_number = ye.employee_number
    and ye.academic_year = {{ var("current_academic_year") }}
where sr.powerschool_teacher_number is not null
```

- [ ] **Step 3: Write the properties YAML** (contract enforced, PK on the
      teacher number).

```yaml
models:
  - name: rpt_gsheets__teacher_roster
    description: >
      Teacher roster for Google Sheets, one row per teacher for the current
      academic year. Joins staff attributes, current-year performance scores,
      and experience. Join partner to rpt_gsheets__assessment_roster via
      powerschool_teacher_number. Race/ethnicity and gender are deliberately
      excluded.
    columns:
      - name: powerschool_teacher_number
        data_type: string
        description: PowerSchool teacher number (PK; join key to the roster).
        data_tests:
          - unique
          - not_null
      - name: academic_year
        data_type: int
        description: Current academic year (start-year integer).
        data_tests:
          - not_null
      - name: job_title
        data_type: string
        description: Current job title.
      - name: level_of_education
        data_type: string
        description: Highest level of education.
      - name: final_score
        data_type: float
        description: Current-year performance management final score.
      - name: final_tier
        data_type: int
        description: Current-year performance management final tier.
      - name: years_at_kipp_total
        data_type: float
        description: Total years at KIPP as of the current year.
      - name: years_experience_total
        data_type: float
        description: Total years of experience as of the current year.
      - name: years_teaching_total
        data_type: float
        description: Total years teaching as of the current year.
```

> Confirm `final_score` / experience columns are `float64` (the spec inventory
> says FLOAT64) and `final_tier` is `int` before relying on these contract
> types.

- [ ] **Step 4: Build and test**

```bash
uv run dbt build --select rpt_gsheets__teacher_roster \
    --project-dir src/dbt/kipptaf --defer --state target/prod
```

Expected: builds; contract enforced; `unique` + `not_null` on
`powerschool_teacher_number` pass. If `unique` fails, the teacher number is not
1:1 after all — switch the PK to `employee_number` (add it as a column) and
re-test, then flag to the spec owner.

- [ ] **Step 5: Lint**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
    src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__teacher_roster.sql \
    src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__teacher_roster.yml
```

- [ ] **Step 6: Commit**

```bash
git add src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__teacher_roster.sql \
        src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__teacher_roster.yml
git commit -m "feat(dbt): add rpt_gsheets__teacher_roster (#4191)"
```

---

## Task 6: Exposures (gated on sheet URLs)

The two `rpt_` models each need a Google Sheets exposure. The destination sheet
URLs are supplied by the owner later, so this task runs once those URLs are in
hand.

**Files:**

- Modify: `src/dbt/kipptaf/models/exposures/google-sheets.yml`

- [ ] **Step 1: Add an exposure block per `rpt_` model.** Fill `url` with the
      owner-provided sheet URL (the only value not derivable now).

```yaml
exposures:
  - name: rpt_gsheets__assessment_roster
    label: Assessment Roster
    type: application
    owner:
      name: Data Team
    depends_on:
      - ref("rpt_gsheets__assessment_roster")
    url: <owner-provided sheet URL>
    config:
      meta:
        dagster:
          kinds: [googlesheets]
  - name: rpt_gsheets__teacher_roster
    label: Teacher Roster
    type: application
    owner:
      name: Data Team
    depends_on:
      - ref("rpt_gsheets__teacher_roster")
    url: <owner-provided sheet URL>
    config:
      meta:
        dagster:
          kinds: [googlesheets]
```

> Match the exact field shape of existing entries in `google-sheets.yml` before
> writing (read the file first) — `kinds`, `owner`, and `type` conventions there
> are authoritative.

- [ ] **Step 2: Parse to validate the exposures resolve**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf
```

Expected: parses with no exposure errors.

- [ ] **Step 3: Lint**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
    src/dbt/kipptaf/models/exposures/google-sheets.yml
```

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/exposures/google-sheets.yml
git commit -m "feat(dbt): add exposures for assessment + teacher rosters (#4191)"
```

---

## Final verification (before PR)

- [ ] Build the full downstream chain to confirm nothing else broke:

  ```bash
  uv run dbt build --select int_assessments__roster_union+ \
      rpt_gsheets__teacher_roster \
      --project-dir src/dbt/kipptaf --defer --state target/prod
  ```

- [ ] Confirm `int_assessments__student_anon_crosswalk` has **no** Google Sheets
      exposure (it is the private decode table).
- [ ] Open the PR using `.github/pull_request_template.md`; body references
      `Closes #4191`. Note in the PR that exposure URLs (Task 6) are pending if
      not yet supplied.

---

## Self-review notes (author)

- **Spec coverage:** crosswalk (Task 1), union of all five sources (Task 3),
  assessment roster view + demographics/course joins + anon swap (Task 4),
  teacher roster (Task 5), exposures (Task 6). All spec sections mapped.
- **Known external dependency:** sheet URLs (Task 6) — the only non-derivable
  inputs; explicitly gated, not a hidden placeholder.
- **Type discipline:** Tasks 3–5 each flag confirming source types before
  locking contract `data_type`s, per the BigQuery numeric/float64 contract trap.
