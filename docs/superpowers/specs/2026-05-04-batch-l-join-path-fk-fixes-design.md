# Batch L — join-path FK fixes design

Closes [#3719](https://github.com/TEAMSchools/teamster/issues/3719),
[#3721](https://github.com/TEAMSchools/teamster/issues/3721),
[#3723](https://github.com/TEAMSchools/teamster/issues/3723).

## Problem

Three open issues in
[PR batch L](https://github.com/orgs/TEAMSchools/projects/4) report
`relationships` test failures where mart-layer join paths cannot resolve foreign
keys:

| Issue | Child column                                                                                                                                                                                                                                                                        | Parent                     | Orphans |
| ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- | ------: |
| #3719 | `fct_assessment_scores_enrollment_scoped.test_date_key`, `fct_assessment_scores_student_scoped.test_date_key`, `dim_school_calendars.date_key`, `fct_behavioral_incidents.close_date_key`, `fct_behavioral_consequences.start_date_key`, `fct_behavioral_consequences.end_date_key` | `dim_dates.date_key`       |     457 |
| #3721 | `dim_course_sections.course_key`                                                                                                                                                                                                                                                    | `dim_courses.course_key`   |  30,241 |
| #3723 | `bridge_student_contacts.student_key`                                                                                                                                                                                                                                               | `dim_students.student_key` |   9,835 |

The three issues share a join-path theme but split into two distinct root
causes.

### Root cause A: dim sourced from enrollment-derived intermediate (#3721, #3723)

Both `dim_courses` and `dim_students` are built from intermediate models scoped
to recent enrollment activity, not from the canonical PowerSchool catalog
tables.

`dim_courses` deduplicates `base_powerschool__course_enrollments` — only courses
with course-enrollment activity in scope appear. `dim_course_sections` sources
from `base_powerschool__sections` and includes every section, so sections whose
course never had an in-scope enrollment have no resolvable `course_key`.

`dim_students` deduplicates `int_extracts__student_enrollments` — only students
with recent enrollments. `bridge_student_contacts` unions PowerSchool contact
rows for every historical student, so contacts for graduated/transferred
students orphan against `dim_students`.

Both dims should be rerouted to source from canonical PowerSchool staging
(`stg_powerschool__courses`, `stg_powerschool__students`). Hash inputs do not
change, so existing FKs from facts continue to resolve.

### Root cause B: junk dates outside the `dim_dates` range (#3719)

`dim_dates` already spans 2000–9999 (`models/marts/dimensions/dim_dates.sql`),
so the orphan `*_date_key` values are not a missing-future-range problem.
Profiling the 457 orphan rows shows three classes of bad value, all upstream
data quality:

- **Year-typo dates** (e.g. `0001-01-01`, `0006-01-01`, `0019-11-12`,
  `0204-01-26`, `1029-12-05`) — user data-entry errors in source systems.
- **Sentinel defaults** — `1900-01-01` (103 rows), `1901-01-15`, `1969-12-31`.
- **Borderline pre-2000** — `1999-12-16` (9 rows from Illuminate). Same source
  as the year-typo dates above; almost certainly also a typo, not legitimate
  Y2K-era testing.

These should be sanitized to NULL at the staging layer where the date
originates. NULL FKs satisfy `relationships`; orphan FKs do not.

## Goals

- All eight originally-failing `relationships` tests return 0 rows.
- Bad dates do not propagate to any consumer (current or future).
- Hash discipline preserved: `student_key` and `course_key` hash inputs do not
  change.
- A regression guard fires if upstream emits new pre-2000 garbage.

## Non-goals

- Active/inactive course filtering on `dim_course_sections`.
- Resolving the survey-fact enrollment-coverage gap (#3794) — same problem
  class, different fix shape, blocked on PR #3793.
- Pushing entity-grain projections from marts into intermediate (#3780).

## Design

### Section 1 — Reroute `dim_courses` to staging (#3721)

Switch `dim_courses` to source from `stg_powerschool__courses` and project the
canonical course attributes directly. The current model deduplicates by
`courses_course_number, _dbt_source_relation`; if `stg_powerschool__courses` is
already grain-correct on the same union key (verify via the staging model's
uniqueness test during implementation), the explicit `dbt_utils.deduplicate` CTE
can be dropped. Otherwise, retain it.

`course_key = generate_surrogate_key(["course_number", "_dbt_source_relation"])`
remains identical, so `dim_course_sections.course_key` and any future course-FK
fact resolve unchanged.

Column mapping (verify against `INFORMATION_SCHEMA.COLUMNS` on
`stg_powerschool__courses` during implementation):

| Mart column        | Staging source                                  |
| ------------------ | ----------------------------------------------- |
| `course_code`      | `course_number` (or staging-renamed equivalent) |
| `course_title`     | `course_name`                                   |
| `credit_type`      | `credittype`                                    |
| `academic_subject` | `discipline`                                    |
| `credits`          | `credit_hours`                                  |

If a staging column is missing or named differently, alias inline.

### Section 2 — Reroute `dim_students` to staging (#3723)

Switch `dim_students` to source from `stg_powerschool__students` (canonical
student catalog including graduated/transferred students PowerSchool retains)
and project the canonical attributes directly.

`student_key = generate_surrogate_key(["student_number"])` remains identical, so
`bridge_student_contacts.student_key` and every student-FK fact resolve
unchanged.

`salesforce_contact_id` is not a PowerSchool attribute. Preserve it via a LEFT
JOIN to the kippadb contact crosswalk (e.g. `stg_kippadb__contact` keyed on
`school_specific_id` / `student_number` — confirm exact key during
implementation).

All other current `dim_students` columns map directly from
`stg_powerschool__students` (or its column-renamed equivalents):
`lea_student_identifier`, `district_student_identifier`,
`state_student_identifier`, `full_name`, `birth_date`, `gender_identity`,
`meal_eligibility_status`, `enrollment_status`, `is_gifted`, `is_ell`,
`has_iep`, `race`. The current `ethnicity → race` CASE expression migrates
verbatim.

The dim grows because graduated/transferred students are now included. That is
the desired outcome; bridges and historical-scope facts resolve their FKs.

### Section 3 — Sanitize pre-2000 dates at staging (#3719)

Apply `if(<col> < date '2000-01-01', null, <col>)` to the date column at the
staging model where each affected fact's date originates. NULL satisfies the
`relationships` test; junk values do not propagate to any other consumer.

Patch sites (final list confirmed during implementation by tracing each fact's
date column upstream):

1. **PowerSchool `calendar_day` staging** — feeds
   `dim_school_calendars.date_key` (3 orphan rows, `1900-01-01`).
2. **DeansList incident staging** — feeds
   `fct_behavioral_incidents.close_date_key` (3 typo-year rows).
3. **DeansList consequence staging** — feeds
   `fct_behavioral_consequences.start_date_key` (1 row) and `end_date_key` (3
   rows).
4. **Illuminate `int_assessments__response_rollup`** — feeds
   `fct_assessment_scores_enrollment_scoped.test_date_key` (~347 rows of typo
   and sentinel values, including the 9 borderline `1999-12-16` rows).
5. **Student-scoped assessment branch** — locate the `1900-01-01` source feeding
   `fct_assessment_scores_student_scoped.test_date_key` (likely Renaissance,
   iReady, or Amplify staging — 100 rows) and sanitize there.

Add a `dbt_utils.expression_is_true` test on each sanitized column at the
staging model:

```yaml
- dbt_utils.expression_is_true:
    arguments:
      expression:
        "{{ column_name }} is null or {{ column_name }} >= '2000-01-01'"
    config:
      severity: error
```

Staging-layer tests must set `severity: error` per project convention. The test
passes immediately after sanitization. If upstream emits new pre-2000 garbage,
the test catches it before it reaches a fact's `relationships` test.

No reusable macro until this pattern recurs in a third domain.

## Implementation sequence

Three logical commits, each independently reviewable:

1. **`dim_courses` reroute.** Switch source, verify column mapping, run
   `relationships` test on `dim_course_sections.course_key` → 0 orphans.
2. **`dim_students` reroute.** Switch source, add kippadb LEFT JOIN for
   `salesforce_contact_id`, verify `bridge_student_contacts.student_key`
   `relationships` → 0 orphans. Spot-check student-FK facts (e.g.
   `fct_assessment_scores_*.student_key`) for unexpected resolution changes.
3. **Date sanitization.** Patch the 4–5 staging sites, add `expression_is_true`
   tests on sanitized columns. Verify all 6 originally-failing date
   `relationships` tests → 0 orphans.

### Hash discipline check

After each reroute, sample 5 known student / course keys before and after to
confirm hash equivalence. The hash inputs are unchanged by design, so this is a
guard against accidental input-list drift during the edit.

### dbt Cloud CI

Standard `dbt build --select state:modified+ --full-refresh` against staging.
The reroutes touch mart sources, not source schemas — no
`stage_external_sources` step required.

### CI warnings audit (mandatory before merge)

After each commit's CI run passes, pull warnings via
`mcp__dbt__get_job_run_error` with `warning_only=true` (success ≠ warning-free,
per `src/dbt/CLAUDE.md`). Diff against the most recent main-branch CI run and
categorize each delta:

- **Bonus closures** — warnings incidentally fixed. Note in PR body and close
  the corresponding issues if any exist.
- **New regressions** — warnings introduced by this commit. Fix before merge.
- **Newly surfaced** — warnings previously masked by the failures this PR
  resolves. File new issues, link to this PR, leave for follow-up batches.

## Acceptance criteria

- [ ] `dim_course_sections.course_key` → `dim_courses.course_key`
      `relationships` test returns 0 rows.
- [ ] `bridge_student_contacts.student_key` → `dim_students.student_key`
      `relationships` test returns 0 rows.
- [ ] All six date `relationships` tests from #3719 return 0 rows.
- [ ] Five new `expression_is_true` tests on sanitized date columns added and
      passing at `severity: error`.
- [ ] Sampled `student_key` and `course_key` values match pre-merge values (no
      hash drift).
- [ ] Post-CI warnings audit completed for each commit; PR body lists bonus
      closures, regressions, and newly-surfaced issues with links.
- [ ] Closes #3719, #3721, #3723.
