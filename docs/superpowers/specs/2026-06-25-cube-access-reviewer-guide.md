# Cube Access Model — Reviewer Guide

Refold-c security redesign · June 2026

## What this is

This document explains how the new Cube access model works and what the values
in `dim_staff_cube_access` mean. It is intended for anyone spot-checking the
access assignments spreadsheet or reviewing the PR before merge.

## How access is resolved

When a staff member queries Cube, the system looks up their Google Workspace
email in `kipptaf_marts.dim_staff_cube_access`. That table has one row per
active, primary-position staff member. Their row determines:

1. **Which views they can see** (column visibility — "tiers")
2. **Which rows they can see** within those views (row-level filters)

If a staff member's email is not found — e.g. a non-staff admin account — they
see nothing. Default deny.

Results are cached until midnight ET each night, so access changes take effect
the next day.

## The two axes of access

### Column visibility (tiers)

Cube views use `access_policy` blocks to gate which fields are visible. A staff
member either has a tier or they do not — there is no partial visibility within
a tier.

| Tier                 | What it unlocks                                                                              |
| -------------------- | -------------------------------------------------------------------------------------------- |
| `staff-directory`    | Every staff member gets this automatically. Name, email, title, location, work contact info. |
| `staff-pii`          | Personal email, personal cell, date of birth, gender identity, race/ethnicity.               |
| `staff-compensation` | Compensation fields (no cube/view built yet — reserved).                                     |
| `staff-observations` | Observation scores and feedback (no cube/view built yet — reserved).                         |
| `staff-benefits`     | Benefits enrollment data (no cube/view built yet — reserved).                                |
| `student-summary`    | Aggregate student metrics (ADA, assessment scores by cohort, enrollment counts).             |
| `student-detail`     | Row-level student data. Includes `student-summary` automatically.                            |
| `student-pii`        | Student names, contact info, and other direct identifiers.                                   |

### Row-level scope (who they can see within a view)

Tiers open up columns. Scope enums determine which _rows_ are returned once a
column is visible.

For **student views**, the scope is a location level — it restricts which
schools' students appear.

For **staff sensitive fields** (PII, compensation, observations, benefits), the
scope is a remit — which staff members the viewer can see sensitive data about.
Two axes intersect: location and department. Both must pass, and the most
restrictive field in a query wins.

## Scope enum glossary

### Location scope (student and staff)

Used by: `student_summary_location_scope`, `student_detail_location_scope`,
`staff_location_scope`

| Value     | What rows are returned                     |
| --------- | ------------------------------------------ |
| `network` | All locations across all regions.          |
| `region`  | Only locations in the viewer's own region. |
| `school`  | Only the viewer's own school.              |
| `none`    | No rows. The tier is not granted.          |

### Department scope (staff only)

Used by: `staff_department_scope`

This works in _combination_ with `staff_location_scope` — both must allow a row
for it to appear.

| Value       | What rows are returned                                                                     |
| ----------- | ------------------------------------------------------------------------------------------ |
| `all`       | All departments within the location scope.                                                 |
| `own_group` | Only staff in the viewer's own `department_group` (e.g. `talent`, `finance`, `academics`). |
| `none`      | No rows. Treated as deny.                                                                  |

### Sensitive field scope (per-field)

Used by: `staff_pii_scope`, `staff_compensation_scope`,
`staff_observations_scope`, `staff_benefits_scope`

These enums set the row filter applied _when that specific sensitive field is in
the query_. If a query includes multiple sensitive fields, the system applies
all their filters — the intersection is what the viewer sees.

| Value                           | Who the viewer can see sensitive data about                                                                                                                    |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `all_in_scope`                  | Anyone within their shared staff remit (location scope ∩ department scope).                                                                                    |
| `teaching_staff`                | Only teachers and teachers-in-residence (`TEACH`, `TIR` job function codes) within their remit.                                                                |
| `reporting_chain`               | Only their direct and indirect reports (transitive org tree from `dim_staff_reporting_chain`).                                                                 |
| `reporting_chain_or_below_rank` | Their reporting chain _plus_ anyone in their remit with a higher `job_function_level` number (i.e. more junior). Level 6 = most junior; level 1 = most senior. |
| `none`                          | No access to this sensitive field.                                                                                                                             |

### Student PII scope

Used by: `student_pii_scope`

| Value  | Meaning                                                                      |
| ------ | ---------------------------------------------------------------------------- |
| `all`  | Student PII fields are visible (subject to the student location row filter). |
| `none` | Student PII is not visible.                                                  |

## Department groups (reference)

The `department_group` column is a coarsened grouping used for `own_group`
department scope checks.

| Value               | Departments it covers                              |
| ------------------- | -------------------------------------------------- |
| `academics`         | Teaching and Learning, Teacher Development         |
| `talent`            | Human Resources, Talent Acquisition                |
| `finance`           | Finance, Accounting, Purchasing                    |
| `school_operations` | Operations, Real Estate and Facilities, Technology |
| `advancement`       | Development, Marketing/Comms/Enrollment            |
| `student_services`  | Special Education, counselors                      |
| `data_technology`   | Data, Technology                                   |
| `kipp_forward`      | KIPP Forward                                       |
| `executive`         | Executive/C-suite                                  |
| `school_leadership` | Principals, APs, KTRGs at the school level         |

## Job function levels (reference)

Higher number = more junior. Used by `reporting_chain_or_below_rank` to
determine who a viewer can see sensitive data about.

| Level  | Typical titles                                      |
| ------ | --------------------------------------------------- |
| 1      | Chief officers, Co-Presidents, Executive Directors  |
| 2      | Managing Directors, EDs/HoS                         |
| 3      | Senior Directors                                    |
| 4      | Directors                                           |
| 5      | Managers, Associates, Specialists (KTRGS)           |
| 6      | Teachers, TIRs, non-instructional staff, counselors |
| `null` | Interns, unmatched roles → no access                |

## Things to flag when spot-checking

- **All `none` scopes**: expected for interns and roles not in the access
  spreadsheet. If a non-intern has all-none, their `job_function_code` may be
  missing from the role sheet.
- **`staff_pii_scope` = `all_in_scope` for HR/Talent**: intentional — HR staff
  need to see PII for their department's staff. Confirm the department override
  row in the spreadsheet covers the right departments.
- **`student_detail_location_scope` = `none` for a regional ops leader**: may be
  intentional (ops directors don't need student row data) — check against their
  role.
- **`null` `job_function_level`**: the role exists but has no level assigned in
  the role sheet. Access will still be granted from the other scope columns, but
  `reporting_chain_or_below_rank` will not work correctly for that person as a
  manager.
