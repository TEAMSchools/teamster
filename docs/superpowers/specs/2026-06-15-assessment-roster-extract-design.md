# Assessment + Teacher Google Sheets Extracts — Design

Issue: [#4191](https://github.com/TEAMSchools/teamster/issues/4191)

Two related Google Sheets extracts delivered on one branch:

1. **Assessment roster** — student/test/round grain (sections below through "Out
   of scope").
2. **Teacher roster** — teacher/year grain; the join partner to model 1's
   `teacher_powerschool_teacher_number` (see "Model 2").

## Context

Ops/academics need a long-format, PII-stripped assessment roster spanning the
current and prior academic year, at student/test/round grain, delivered to a
Google Sheet. It unifies five assessment sources (i-Ready, Miami FAST, DIBELS,
NJSLA, internal assessments) into one schema and ties each result to the
student's ELA/Math course enrollment (teacher, course, section) and core
demographics.

PII is stripped: the sheet carries a stable anonymized student id, never
`student_number`. A separate internal crosswalk lets the owner decode the anon
id back to `student_number` inside BigQuery.

## Decisions

- **Architecture:** union intermediate + thin reporting view (Approach B), per
  the kipptaf rule that an `rpt_*` view must buffer an intermediate from any
  external consumer.
- **Anon id:** stable **salted** hash of `student_number` in the sheet —
  `generate_surrogate_key(['student_number', '<salt>'])`, where the salt is read
  from `env_var('STUDENT_ANON_SALT')` (a dev/CI default; the real secret is
  provisioned only in the prod runtime and never committed). Salting closes the
  brute-force hole: an unsalted MD5 of a low-entropy `student_number` is
  trivially reversible by anyone who knows the (public) method. A separate
  internal-only crosswalk model maps the id back to `student_number`; it gets no
  Google Sheets exposure. The salt must stay constant in prod — changing it
  re-anonymizes every student.
- **Performance columns:** two columns — `performance_band_label` (string, e.g.
  "Mid or Above Grade Level") and `performance_band_int` (integer, e.g. 5). Both
  are native to each source; no new standardized scale is invented.
- **Course-enrollment join:** LEFT join — never drop a score. Teacher / course /
  section are null when no matching ENG/MATH course exists.
- **Round:** each source's native window label passes through verbatim. Internal
  assessments use `module_code` for `administration_round`.
- **Two-year window:** `academic_year in ({{ current_academic_year }}, {{`
  `current_academic_year }} - 1)` — driven by the variable, not hardcoded, so it
  rolls forward each July. NJSLA is restricted to the prior year only.

## Models

### 1. `int_assessments__roster_union`

Location: `src/dbt/kipptaf/models/assessments/intermediate/`. Normalizes and
stacks the five sources into the common schema below. Carries `student_number`
(no PII swap at this layer). Uniqueness test on the row grain.

**Grain / PK:** one row per
`student_number × assessment_source × subject × administration_round ×`
`assessment_id`. `assessment_id` is null for benchmark/state sources (one score
per round) and the Illuminate `assessment_id` for internal assessments (many per
term). PK = `generate_surrogate_key` over those fields with a sentinel for null
`assessment_id`.

**Common schema and per-source derivation:**

| Union column             | i-Ready                          | FAST (FLDOE)             | DIBELS (Amplify)             | NJSLA (Pearson)             | Internal (response_rollup)      |
| ------------------------ | -------------------------------- | ------------------------ | ---------------------------- | --------------------------- | ------------------------------- |
| `assessment_source`      | `'i-Ready'`                      | `'FAST'`                 | `'DIBELS'`                   | `'NJSLA'`                   | `'Internal'`                    |
| `student_number`         | `student_id` (verify)            | `student_number`         | `student_number`             | `localstudentidentifier`    | `powerschool_student_number`    |
| `academic_year`          | `academic_year_int`              | `academic_year`          | `academic_year`              | `academic_year`             | `academic_year`                 |
| `subject`                | Reading→ELA, Math→Math           | `illuminate_subject` map | `'ELA'`                      | `illuminate_subject` map    | `discipline` (ELA/Math)         |
| `administration_round`   | `test_round`                     | `administration_window`  | `period`                     | `admin` (`'Spring'`)        | `module_code`                   |
| `assessment_id`          | null                             | null                     | null                         | null                        | `assessment_id`                 |
| `assessment_title`       | null                             | null                     | null                         | null                        | `title`                         |
| `scale_score`            | `overall_scale_score`            | `scale_score`            | `measure_standard_score`     | `testscalescore`            | null                            |
| `percent_correct`        | null                             | null                     | null                         | null                        | `percent_correct`               |
| `is_proficient`          | `is_proficient`                  | `is_proficient`          | derived (see below)          | `is_proficient`             | `is_mastery`                    |
| `performance_band_label` | `overall_relative_placement`     | `achievement_level`      | `measure_standard_level`     | `testperformancelevel_text` | `performance_band_label`        |
| `performance_band_int`   | `overall_relative_placement_int` | `performance_level`      | `measure_standard_level_int` | `testperformancelevel`      | `performance_band_label_number` |

**Per-source filters (inside the union):**

- **i-Ready:** subject in (Reading, Math); model already windows to one row per
  subject/year/round.
- **FAST:** Miami only (natural); `illuminate_subject` in (Text Study,
  Mathematics).
- **DIBELS:** `assessment_type = 'Benchmark'` and `measure_standard =`
  `'Composite'` (overall score, one per round); excludes PM rows.
- **NJSLA:** `assessment_name = 'NJSLA'` only (excludes PARCC, NJGPA, NJSLA
  Science); prior year only.
- **Internal:** `module_type in ('QA','MQQ','CRQ')` and `response_type =`
  `'overall'`; `discipline in ('ELA','Math')`.
- **All sources:** `academic_year` within the two-year window;
  `subject in ('ELA','Math')`.

**DIBELS proficiency derivation:** no native boolean — derive `is_proficient`
from `aggregated_measure_standard_level` (`'At/Above'` → true, else false).

### 2. `int_assessments__student_anon_crosswalk`

Location: `src/dbt/kipptaf/models/assessments/intermediate/`. One row per
`student_number`:

```sql
select distinct
    student_number,
    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "'" ~ env_var("STUDENT_ANON_SALT", "dev_salt") ~ "'"]
        )
    }} as student_anon_id
from <enrollment population>
```

The salt is appended as a quoted string literal inside the hash inputs.
`env_var("STUDENT_ANON_SALT", "dev_salt")` falls back to `dev_salt` for local
and dbt Cloud CI (throwaway schemas), so those builds never break; the real
secret is set only in the prod runtime environment (Dagster deployment / secret
bootstrap) and must remain constant. Internal-only decode table — **no Google
Sheets exposure.** Decode usage:
`select student_number from <crosswalk> where student_anon_id = '<id>'`.

### 3. `rpt_gsheets__assessment_roster`

Location: `src/dbt/kipptaf/models/extracts/google/sheets/`. View (extract
default). Joins demographics + course enrollment onto the union, swaps
`student_number` for `student_anon_id`, drops `student_number`, and selects the
final sheet columns.

**Joins:**

- Demographics ← `int_extracts__student_enrollments_subjects` on
  `student_number` + `academic_year` (scopes to enrolled K-8).
- Teacher/course/section ← `base_powerschool__course_enrollments` on
  `student_number` + `academic_year`, with `rn_credittype_year = 1`,
  `not is_dropped_section`, `credittype in ('ENG','MATH')`, and `credittype`
  matched to `subject` (ELA→ENG, Math→MATH). LEFT join.
- Anon id ← crosswalk on `student_number`.

**Scope:** grade `K-8` (`grade_level between 0 and 8`); population = students
present in the demographics model within the two-year window.

**Final sheet columns:**

| Column                               | Source                                |
| ------------------------------------ | ------------------------------------- |
| `student_anon_id`                    | crosswalk (replaces `student_number`) |
| `academic_year`                      | union                                 |
| `region`                             | demographics                          |
| `school_abbreviation`                | demographics (verify column name)     |
| `grade_level`                        | demographics                          |
| `iep_status`                         | demographics                          |
| `ml_status`                          | demographics (`lep_status`)           |
| `status_504`                         | demographics                          |
| `assessment_source`                  | union                                 |
| `subject`                            | union                                 |
| `administration_round`               | union                                 |
| `assessment_title`                   | union (internal only)                 |
| `teacher_powerschool_teacher_number` | `teachernumber`                       |
| `course_number`                      | `cc_course_number`                    |
| `section_number`                     | `cc_section_number`                   |
| `scale_score`                        | union                                 |
| `percent_correct`                    | union (internal only)                 |
| `is_proficient`                      | union (mastery/proficiency boolean)   |
| `performance_band_label`             | union                                 |
| `performance_band_int`               | union                                 |

## Exposure

Add `rpt_gsheets__assessment_roster` to
`src/dbt/kipptaf/models/exposures/google-sheets.yml` with the standard required
fields. The Google Sheets URL will be provided by the owner later; the exposure
lands once the URL is known.

## Testing

- `int_assessments__roster_union`: `dbt_utils.unique_combination_of_columns` on
  the grain (or `unique` on the surrogate PK); `not_null` on PK,
  `student_number`, `academic_year`, `assessment_source`, `subject`.
- `int_assessments__student_anon_crosswalk`: `unique` + `not_null` on
  `student_number` and `student_anon_id`.
- `rpt_gsheets__assessment_roster`: contract enforced (extracts default);
  uniqueness test on the row grain; `not_null` on `student_anon_id`.
- Build/validate with `uv run dbt build --select int_assessments__roster_union+`
  against kipptaf.

## Verification items

- i-Ready `student_id` is the PowerSchool `student_number` — confirmed; join
  directly.
- Demographics column is `school_abbreviation` — confirmed.
- During implementation: confirm the NJSLA subject mapping from
  `illuminate_subject` covers only ELA & Math (exclude science).

## Out of scope (model 1)

- Backfill/Dagster scheduling beyond the standard dagster-dbt asset pickup.

## Model 2 — teacher roster extract

### Overview

`rpt_gsheets__teacher_roster` — a standalone Google Sheets extract at
teacher/year grain, joining staff attributes, current-year performance scores,
and experience. It is the join partner to model 1 via
`powerschool_teacher_number`. Race/ethnicity and gender are deliberately
excluded from the sheet.

### Decisions (model 2)

- **Architecture:** a single reporting view. The base
  (`int_people__staff_roster_history`, pinned to a point in time) is
  teacher-grain, so the `rpt_` view refs the intermediates and joins them — no
  union or new intermediate needed, and the `rpt`-buffers-intermediate rule is
  satisfied on its own.
- **Base source — point-in-time history, not the live snapshot.** Use
  `int_people__staff_roster_history` filtered to `primary_indicator` and an
  as-of date, NOT `int_people__staff_roster`. The live snapshot surfaces _next_
  year's `job_title` once summer reassignments are entered; the history table
  pinned to the school year returns the correct title.
- **As-of date — variable-derived, not hardcoded.**
  `date({{ current_academic_year }} + 1, 4, 1)` (April 1 of the current school
  year's spring). Rolls forward each July, consistent with model 1's
  no-hardcoding rule. The `between` must coalesce an open `effective_date_end`
  (`coalesce(effective_date_end, '9999-12-31')`) so the live record isn't
  dropped.
- **Year:** `var("current_academic_year")` for the perf/experience joins (not
  hardcoded), so it rolls forward each July.
- **Population:** teachers only (`powerschool_teacher_number is not null`).
- **PII:** race/ethnicity and gender excluded; teacher is identified by
  `powerschool_teacher_number` (the intended join key to model 1).
  `reports_to_employee_number` (manager id, not protected-class) is included.

### Grain (model 2)

One row per `powerschool_teacher_number` for the current academic year.

### Joins (model 2)

- Base: `int_people__staff_roster_history`, filtered to `primary_indicator`,
  `powerschool_teacher_number is not null`, and
  `date({{ current_academic_year }} + 1, 4, 1) between effective_date_start and`
  `coalesce(effective_date_end, '9999-12-31')` — one row per employee as of that
  date.
- LEFT join `int_performance_management__overall_scores` on `employee_number`
  and `academic_year = var("current_academic_year")`.
- LEFT join `int_people__years_experience` on `employee_number` and
  `academic_year = var("current_academic_year")`.

Left joins so a teacher with no current-year score/experience still appears
(null metrics).

### Final sheet columns (model 2)

| Column                       | Source                                      |
| ---------------------------- | ------------------------------------------- |
| `powerschool_teacher_number` | staff_roster_history (PK / join to model 1) |
| `academic_year`              | `var("current_academic_year")`              |
| `job_title`                  | staff_roster_history (as-of date)           |
| `level_of_education`         | staff_roster_history                        |
| `reports_to_employee_number` | staff_roster_history (manager id)           |
| `final_score`                | overall_scores                              |
| `final_tier`                 | overall_scores                              |
| `years_at_kipp_total`        | years_experience                            |
| `years_experience_total`     | years_experience                            |
| `years_teaching_total`       | years_experience                            |

### Testing (model 2)

Contract enforced (extracts default); `unique` + `not_null` on the PK;
`not_null` on `academic_year`. Build with
`uv run dbt build --select rpt_gsheets__teacher_roster` against kipptaf.

### Verification items (model 2)

- `powerschool_teacher_number` is 1:1 with teachers — confirmed; it is the PK.
- During implementation: confirm the `primary_indicator` + as-of-date filter on
  `int_people__staff_roster_history` yields exactly one row per
  `powerschool_teacher_number` (the PK uniqueness test will catch a violation).

### Exposure (model 2)

Add `rpt_gsheets__teacher_roster` to
`src/dbt/kipptaf/models/exposures/google-sheets.yml`; URL provided later.

### Out of scope (model 2)

- Race/ethnicity and gender columns (deliberately excluded).
- Multi-year history — the roster is pinned to a single as-of date per the
  current academic year, not a per-year time series.
