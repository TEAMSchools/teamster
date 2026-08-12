# DeansList missing-assignments feed: re-point onto the gradebook audit lineage

Issue: [#4849](https://github.com/TEAMSchools/teamster/issues/4849)

## Problem

`rpt_deanslist__missing_assignments` selects six columns from
`rpt_tableau__gradebook_assignments` where `ismissing = 1` and
`finalgrade_category = 'Q'`. That upstream view is pre-AY2627: it last changed
in 2023, has no exposure, is absent from the gradebook audit reference doc, and
reaches assignments through `int_powerschool__section_grade_config` rather than
through the audit's assignment model.

The AY2026-2027 gradebook audit revamp moved assignment tracking to
`int_powerschool__gradebook_assignments_scores` (one row per student per
assignment) and its per-assignment rollup. The DeansList feed never followed, so
the two surfaces now disagree about which assignments exist and what counts as
missing.

Measured against AY2025 prod data, the feed diverges from the audit as follows:

| Divergence                                                | AY2025 rows                                  |
| --------------------------------------------------------- | -------------------------------------------- |
| Paterson structurally excluded                            | 3,267 never shipped                          |
| Miami still included                                      | 14,307                                       |
| Exempt assignments reported missing                       | 10,980                                       |
| Not-counted-in-final-grade assignments reported missing   | 2,029                                        |
| Assignments due outside the student's enrollment window   | 14,020                                       |
| Dropped-section enrollments                               | 25,760                                       |
| Duplicate records from the `section_grade_config` fan-out | 9,628 (260,945 rows, 251,317 distinct pairs) |

The Paterson gap cannot be fixed in place.
`int_powerschool__section_grade_config` unions Newark, Camden and Miami only,
and Paterson's district copy is deliberately disabled — `gradesectionconfig` is
empty in Paterson's PowerSchool, recorded as a data-forced exception in
`kipppaterson/dbt_project.yml`. Any feed built on that model excludes Paterson
permanently.

The feed is also an `rpt_` reading an `rpt_`, the layering violation the July
2026 teacher/student split removed from the audit reports.

## Decisions

Missing means `is_expected_missing` — the audit's definition, which requires the
assignment to be neither exempt nor excluded from the final grade. This is the
change that makes DeansList and the dashboard agree.

Miami is excluded. Miami is off DeansList, and its gradebook moved to Focus, so
its PowerSchool assignments will go stale rather than error.

ES is excluded. ES schools do not use PowerSchool for assignments; they get
end-of-quarter comments only, via `rpt_tableau__gradebook_es_comments`.

Single-quarter-term sections stay in. The audit excludes them upstream through
`int_extracts__course_schedule_by_term`, but that exclusion scopes which
gradebooks are audited against per-quarter assignment-count expectations. It has
no bearing on whether a student turned work in, so importing it into a
student-follow-up feed would hide 3,624 AY2025 rows of real missing work.

`rpt_tableau__gradebook_assignments` is disabled, not deleted. Retiring a model
in this repo is always a disable — the SQL stays in the tree and the relation
stays queryable, so a consumer nobody knew about degrades to frozen data rather
than vanishing.

It is safe to retire: it carries no dbt exposure, there is no Tableau extract
config for it (only Clever, DeansList and Illuminate exist), and after the
re-point nothing in the repo references it — verified across `.sql`, `.yml`,
`.yaml`, `.py` and `.md`, with the only remaining mention a historical plan
document.

A disabled model stops rebuilding but does not drop its relation, so the prod
view is left in place. No `drop view` is issued.

## Design

Target lineage:

```text
int_powerschool__gradebook_assignments  ─┐
base_powerschool__course_enrollments ────┼─► int_powerschool__gradebook_assignments_scores
stg_powerschool__assignmentscore ────────┘        │
                                                  ├─► int_powerschool__gradebook_assignment_scores_rollup
                                                  ├─► fct_grades_assignments
                                                  └─► rpt_deanslist__missing_assignments
```

### Change 1: project label columns on the assignments model

`int_powerschool__gradebook_assignments_scores` already inner-joins
`base_powerschool__course_enrollments`, which carries every label the feed
needs. Add three passthrough columns to the `scores` CTE and the final select:

| New column       | Source                      |
| ---------------- | --------------------------- |
| `student_number` | `e.students_student_number` |
| `course_name`    | `e.courses_course_name`     |
| `teacher_name`   | `e.teacher_lastfirst`       |

Safe to add: both live consumers project explicit column lists rather than
`select *` — the rollup aggregates to `assignmentsectionid` grain, and
`fct_grades_assignments` enumerates its columns. The model is a view, so there
is no rebuild cost. Add the three columns to its properties yml.

The columns are already in scope of the model's existing join, so projecting
them adds no rows. Verified by re-running the join separately against AY2025
prod: the feed population came back at 209,311 rows with and without it.

`student_number` is a direct identifier and stops here: the rollup aggregates
students away, so no student PII reaches `rpt_tableau__gradebook_audit`. Review
whether the model needs `config.meta.contains_pii` during implementation.

### Change 2: rewrite the DeansList feed

`rpt_deanslist__missing_assignments` reads
`int_powerschool__gradebook_assignments_scores` with these filters:

```sql
where
    academic_year = {{ var("current_academic_year") }}
    and is_expected_missing = 1
    and _dbt_source_project != 'kippmiami'
    and school_level_alt != 'ES'
```

Column mapping from the existing feed:

| Feed column           | Was                                              | Becomes               |
| --------------------- | ------------------------------------------------ | --------------------- |
| `student_number`      | `int_extracts__student_enrollments`              | `student_number`      |
| `grade_category`      | `int_powerschool__section_grade_config` category | `category_name`       |
| `assign_name`         | assignment `name`                                | `assignment_name`     |
| `assign_date`         | assignment `duedate`                             | `duedate`             |
| `course_name`         | `courses_course_name`                            | `course_name`         |
| `teacher_name`        | `teacher_lastfirst`                              | `teacher_name`        |
| `assignmentsectionid` | not projected                                    | `assignmentsectionid` |

`grade_category` is the one real provenance change: it moves from the section's
grade configuration to the assignment's own category, which is where the audit
reads it.

The `finalgrade_category = 'Q'` filter is dropped and not replaced. It existed
only to collapse the storecode fan-out; per-assignment rows carry no storecode.

`assignmentsectionid` is a new seventh column, added so the uniqueness test has
a key to run on. Approved by the DeansList owner.

Add the uniqueness test:

```yaml
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns:
          - student_number
          - assignmentsectionid
      config:
        severity: error
```

Both columns are in the projection, so the feed grows by exactly one column and
no others. The key omits `_dbt_source_project`, which means it relies on
`student_number` being unique network-wide rather than per region — verified
exactly unique on AY2025 data (209,311 rows, 209,311 distinct pairs). If a
future region ever reuses student numbers, this test is where it surfaces.

### Change 3: disable the legacy view

Add `config: enabled: false` to
`extracts/tableau/properties/rpt_tableau__gradebook_assignments.yml`. The model
carries no data tests, so there are no test nodes needing the same treatment.
Leave the `.sql` and the prod view in place.

## Expected output

AY2025 shape under the new lineage, for comparison against the build:

| Region   | Rows    |
| -------- | ------- |
| Newark   | 139,704 |
| Camden   | 66,340  |
| Paterson | 3,267   |
| Total    | 209,311 |

Against the legacy path's 260,945 rows for Newark, Camden and Miami with no
Paterson. Both `(student_number, assignmentsectionid)` and
`(_dbt_source_project, students_dcid, assignmentsectionid)` are exactly unique
across all three regions in that data; the test uses the former because both its
columns are already projected.

Note that `(students_dcid, assignmentid)` is **not** unique — 119 AY2025 pairs
repeat, because PowerSchool shares one `assignmentid` across sections and gives
each section its own `assignmentsectionid`. That is why the test keys on
`assignmentsectionid`.

## Validation

1. Build `int_powerschool__gradebook_assignments_scores`, then the rollup, then
   `rpt_tableau__gradebook_audit` and `rpt_deanslist__missing_assignments`, one
   at a time.

1. Confirm the rollup and `fct_grades_assignments` are unchanged. Adding columns
   to a model whose consumers project explicit lists must be a no-op; compare
   row counts and distinct-key counts against prod.

1. Confirm the uniqueness test passes on the new feed.

1. Compare the feed's row count and region split against the Expected output
   table. The current academic year holds no assignments yet, so validate
   against AY2025 by temporarily overriding the year var, not by trusting an
   empty build.

## Out of scope

`fct_grades_assignments` re-joins `base_powerschool__course_enrollments` for
labels this change makes available on `_scores`. Simplifying that mart is a
separate, unrelated cleanup.

The gradebook audit reference doc states the audit's single-quarter section
filter has no recoverable business rationale. The data team says there is one.
Correcting that passage is worth doing but belongs in its own change.
