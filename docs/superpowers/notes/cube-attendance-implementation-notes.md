# Cube Attendance Implementation Notes

Running log of decisions made while translating the POC `fct_attendance` cube to
the production `attendance.yml` based on `fct_student_attendance_daily`.

---

## ADA measure: ratio formula instead of `type: avg`

**POC:** `type: avg` on `is_present` filtered to `membership_value = 1`

**New:** `SUM(attendance_value) / SUM(membership_value)` via two private helper
measures (`_sum_attendance_value`, `_sum_membership_value`) and a `type: number`
calculated measure.

**Why:** `type: avg` computes `SUM / COUNT(rows)`, not `SUM / SUM(membership)`.
These are equivalent only when all `membership_value` rows are exactly `1.0`.
The correct ADA formula always divides by total membership weight, which handles
dual-enrollment (fractional membership) correctly.

**Data check (2026-04-29):** `fct_student_attendance_daily` has only `0` and `1`
membership values today (12.8M rows at `1`, 78K rows at `0`). No fractional
values exist. The formula change produces identical results against current data
but is semantically correct and won't silently break if fractional membership
appears.

---

## `membership_value` filter: `> 0` instead of `= 1`

**POC:** `membership_value = 1` on all measure filters.

**New:** `> 0` on `count_students`; `= 1` retained on `pct_tardy`,
`count_truants` pending the same review.

**Why:** `> 0` expresses the intent ("days when the school has a membership
claim") rather than assuming the only valid value is `1`. Functionally identical
today — see data check above.

**Deferred:** Apply the same `> 0` treatment to `pct_tardy` and `count_truants`
filters; also evaluate whether those measures should use a `SUM/SUM` ratio for
the same dual-enrollment reason as ADA.

---

## Joins restructured

| POC join                          | Status   | Reason                                                                                                                    |
| --------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------- |
| `dim_dates` (via `FILTER_PARAMS`) | Replaced | `FILTER_PARAMS` is Cube Cloud v1 syntax; replaced with standard equality join on `date_day = CAST(date_key AS TIMESTAMP)` |
| `dim_students`                    | Removed  | Strict-chain violation — fact FKs to `dim_student_enrollments`, not `dim_students` directly                               |
| `fct_attendance_communications`   | Removed  | No equivalent in the new mart design; belongs in future `attendance_interventions.yml`                                    |
| `dim_locations`                   | Added    | FK exists on fact; was missing from POC                                                                                   |
| `dim_student_enrollments`         | Added    | Direct FK parent of the fact                                                                                              |
| `dim_terms`                       | Added    | FK exists on fact; was missing from POC                                                                                   |
| `dim_school_calendars`            | Added    | Compound `(date_key, location_key)` join per spec — avoids diamond path through `dim_locations`                           |

---

## Window functions moved to dbt

**POC:** `rolling_avg_attendance_student`, `is_truant_latest`, and
`is_chronic_absentee_latest` computed via window functions inside the Cube
`sql:` block using `FILTER_PARAMS`.

**New:** `is_truant` is already a row-level column on the mart, computed at the
intermediate layer with the same running-window logic. No Cube window functions
needed.

**Chronic absentee (deferred):** `is_chronic_absent` does not yet exist on the
mart. To be added to `int_powerschool__ps_adaadm_daily_ctod` using the same
running-window pattern as `is_truant` (YTD `AVG(attendance_value) < 0.90`). Once
the dbt column exists, add to `attendance.yml`:

```yaml
- name: count_chronic_absentees
  sql: student_enrollment_key
  type: count_distinct
  filters:
    - sql: "{CUBE}.is_chronic_absent = true"
    - sql: "{CUBE}.membership_value > 0"

- name: pct_chronic_absentee
  sql: "1.0 * {count_chronic_absentees} / NULLIF({count_students}, 0)"
  type: number
  format: percent
```

**Point-in-time caveat (applies to truancy and chronic absentee):** These flags
are cumulative running values. In a date range query, `count_truants` /
`count_chronic_absentees` count students who were flagged on _any_ day in the
range, not just the last day. For a true snapshot, filter to a single date.

---

## Column changes

| POC column            | New column                     | Note                                              |
| --------------------- | ------------------------------ | ------------------------------------------------- |
| `is_present_weighted` | `present_weight`               | Renamed in mart                                   |
| `student_number`      | (removed)                      | Plumbing — access via `dim_student_enrollments`   |
| `term`                | (removed)                      | Access via `dim_terms`                            |
| `attendance_key` (PK) | `student_attendance_daily_key` | New PK name in mart                               |
| (missing)             | `attendance_category`          | New column in mart — coarse category for GROUP BY |
| (missing)             | `attendance_value`             | Explicit attendance credit column                 |

---

## `dim_dates` join scope: attendance date only

The `attendance → dim_dates` join filters the **attendance fact's own date**
(`fct_student_attendance_daily.date_key`). It does not affect enrollment
boundary dates (`entry_date_key`, `exit_date_key` on `dim_student_enrollments`)
or any other date columns on joined dimensions.

`entry_date` and `exit_date` in `student_enrollments.yml` are exposed as inline
`CAST(... AS TIMESTAMP)` time dimensions. This supports range filters ("students
who enrolled after X") without a `dim_dates` join. It does NOT provide
date-attribute grouping (month of entry, academic year of exit) because Cube
only allows one join per named cube and both FKs point at `dim_dates` —
declaring either one would leave the other unjoinable.

This is not a gap for attendance metrics: `dim_student_enrollments` already
carries `academic_year` and `grade_level` as its own columns (the most common
grouping axes), and attendance date grouping always travels through the fact's
own `dim_dates` join. If month-of-enrollment grouping is ever needed, it can be
derived inline: `sql: EXTRACT(MONTH FROM entry_date_key), type: number`.

---

## `pct_successful_attendance_calls` deferred

POC had this measure referencing `fct_attendance_communications.is_successful`.
No equivalent exists in the new mart design. Natural home is
`attendance_interventions.yml` once that cube is built over
`fct_student_attendance_interventions`.

---

## `public: false` required on all cubes

All cubes must set `public: false`. Without it, users can query the underlying
cube directly, bypassing any `access_policy` restrictions defined on views.
Applied to: `attendance.yml`, all conformed cubes (`dates`, `locations`,
`regions`, `school_calendars`, `terms`), and all student cubes
(`student_enrollments`, `students`).

---

## `{CUBE}` alias required in SQL expressions

Dimension/measure `sql:` blocks must use `{CUBE}.column_name`, never
`table_name.column_name`. Hardcoded table names break inside Cube's generated
subqueries. Fixed on: `locations.yml` (`name` column), `regions.yml` (`name`),
`terms.yml` (`type`).

---

## `access_policy` hides views from schema entirely

`access_policy` in view YAML is not just a row/column filter — it controls
schema visibility. If `contextToGroups` returns `[]` (e.g., API token auth with
no user email), the view is hidden from the schema entirely. This caused "No
Semantic Views" in the GSheets plugin.

`attendance_summary` has `access_policy: cube-access-student-data`. This is
correct because the view contains demographic breakdowns. Users without the
group see no schema entry for the view, which is the intended behavior once the
Directory API is live.

`attendance_detail` retains `access_policy` for the same reason (plus it
contains PII fields).

---

## Cube Cloud SSO email path

Cube Cloud SSO injects user identity at
`securityContext.cubeCloud.userAttributes.email`, not `securityContext.email`.
Both `resolveGroupsSync` and `contextToGroups` must fall back to this path:

```js
const email =
  securityContext?.email ?? securityContext?.cubeCloud?.userAttributes?.email;
```

JWT playground auth uses `securityContext.email` (or `securityContext.groups`
for the pass-through). GSheets plugin SSO uses the `cubeCloud` path.

---

## contextToGroups → queryRewrite bridge via groupCache

`contextToGroups` (async) runs before `queryRewrite` (sync) in Cube Cloud. The
results are NOT automatically injected back into `securityContext.groups`.
`groupCache` is the bridge: `contextToGroups` populates it, `resolveGroupsSync`
reads from it.

`resolveGroupsSync` checks in priority order:

1. `securityContext.groups` — JWT claims (playground) or direct injection
2. `groupCache` — populated by `contextToGroups` (Cube Cloud production path)
3. `CUBE_GROUP_MAP` — local dev only, synchronous bypass

All three paths must resolve email via the `cubeCloud` fallback (step 2 above).

---

## `membership_value` filter alignment (follow-up)

`count_truants` currently uses `membership_value = 1`; `count_students` uses
`> 0`. These should be aligned to `> 0` for consistency with the denominator.
Also evaluate whether `pct_tardy` should use a `SUM/SUM` ratio like ADA (same
dual-enrollment correctness argument).
