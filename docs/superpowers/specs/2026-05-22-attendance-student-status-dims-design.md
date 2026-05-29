# Attendance Cube — Student Status Dimensions Design

**Date:** 2026-05-22 **Status:** Approved

## Overview

Add point-in-time ELL, IEP, and meal eligibility status dimensions to the
attendance Cube views. Replaces the current-state `is_ell` flag (sourced from
`dim_students`) with historically accurate status derived from three new SCD2
dimension models that landed in dbt (PR #3985).

## Goals

- Expose `is_ell`, `is_iep`, `iep_classification`, NJ sped codes,
  `is_meal_eligible`, and `meal_eligibility` in both `student_attendance_detail`
  and `student_attendance_summary` views
- Status reflects the student's classification on the specific attendance date,
  not their current status today
- Follow existing Cube patterns: private cubes, public views, `prefix: true`
  naming

## Non-goals

- A standalone `student_status_history` cube (no attendance anchor) — separate
  spec
- Pre-aggregations — follow-up
- Paterson/Miami-specific sped code columns (not in source data for those
  regions)

## Design

### Pattern choice

Three direct `many_to_one` joins from the `attendance` cube using date-range
predicates. Pattern 3 (SCD2 period intersection domain cubes) from the
[cube model YAML design spec](2026-04-17-cube-model-yaml-design.md) was
considered and rejected: it applies to cubes without a single event date, where
multiple SCD2 children could drift to different effective periods. The
attendance fact already has one event date per row; all three status joins
anchor to the same `date_key`, so no period intersection is needed.

### Join predicate (per status dim)

```yaml
sql: >
  {dim_student_ell_status.student_enrollment_key} =
  {CUBE}.student_enrollment_key AND {CUBE}.date_key >=
  {dim_student_ell_status.effective_date_start_key} AND {CUBE}.date_key <=
  {dim_student_ell_status.effective_date_end_key}
relationship: many_to_one
```

`many_to_one` is safe because the dbt non-overlapping-spans uniqueness tests
guarantee at most one status row per enrollment per date. Cube's default LEFT
JOIN for `many_to_one` means dates with no matching span return NULL — treated
as not ELL / not IEP / not meal-eligible in BI tools.

### Access policy

New dimensions are categorical status attributes (same tier as `race`,
`gender_identity`, `is_gifted`). No `access_policy` changes needed — they
inherit `*` under `cube-access-student-data` and are not direct identifiers
under FERPA.

### `cube.js`

The three new cube names are added to `STUDENT_CUBES` so `queryRewrite` gates
them behind `cube-access-student-data`.

## Files changed

| File                                                 | Change                                                                  |
| ---------------------------------------------------- | ----------------------------------------------------------------------- |
| `cubes/students/student_ell_status.yml`              | New                                                                     |
| `cubes/students/student_iep_status.yml`              | New                                                                     |
| `cubes/students/student_meal_eligibility_status.yml` | New                                                                     |
| `cubes/attendance/attendance.yml`                    | 3 new joins                                                             |
| `views/attendance/student_attendance_detail.yml`     | Remove `dim_students.is_ell`; add 3 join paths + `meta.folders` entries |
| `views/attendance/student_attendance_summary.yml`    | Same                                                                    |
| `cube.js`                                            | `STUDENT_CUBES` += 3 new cube names                                     |
