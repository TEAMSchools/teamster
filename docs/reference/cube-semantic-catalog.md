# Cube semantic layer — catalog

What the KIPP TEAM & Family semantic layer exposes, for teams building against
it.

**There is no data on this page.** It describes views, dimensions, and measures
only.

The machine-readable form of the same content is published alongside this page
at `cube-catalog-meta.json` — parse that, not this page. Both are generated from
the deployed model by `scripts/cube_catalog_export.py`; regenerate both after a
model change so the diff is reviewable.

## How you query it

One `POST` per query to `/cubejs-api/v1/load`, with a JSON query object.

- The `Authorization` header takes the **raw token — no `Bearer` prefix.** This
  is the single most common setup mistake.
- Tokens are short-lived and obtained per session from the token-exchange
  service. You never hold a signing secret.
- **Row and field access is derived server-side from the caller's identity.**
  You pass an identity; you never pass or compute a scope.

### The query object

```json
{
  "measures": ["staff_directory.count_employees"],
  "dimensions": ["staff_directory.regions_region_name"],
  "filters": [
    {
      "member": "staff_directory.is_primary_position",
      "operator": "equals",
      "values": ["true"]
    }
  ],
  "timeDimensions": [
    {
      "dimension": "staff_directory.dates_date_day",
      "dateRange": ["2026-08-05", "2026-08-05"]
    }
  ],
  "order": { "staff_directory.count_employees": "desc" },
  "limit": 10
}
```

Every member name is dotted `view.member`. Bare member names do not resolve.

### The response envelope

Values below are illustrative, not real.

```json
{
  "query": { "...": "your query, normalized — see gotcha 5" },
  "lastRefreshTime": "2026-08-06T21:08:20.474Z",
  "annotation": {
    "measures": {
      "staff_directory.count_employees": {
        "title": "Staff Directory Count Employees",
        "shortTitle": "Count Employees",
        "description": "Distinct employees in scope...",
        "type": "number"
      }
    },
    "dimensions": {
      "staff_directory.regions_region_name": {
        "title": "Staff Directory Regions Region Name",
        "shortTitle": "Regions Region Name",
        "description": "Region name (Camden, Miami, Newark, Paterson, TAF).",
        "type": "string"
      }
    },
    "segments": {},
    "timeDimensions": {}
  },
  "dataSource": "default",
  "dbType": "bigquery",
  "extDbType": "cubestore",
  "external": false,
  "slowQuery": false,
  "data": [
    {
      "staff_directory.regions_region_name": "Region A",
      "staff_directory.count_employees": "900"
    },
    {
      "staff_directory.regions_region_name": null,
      "staff_directory.count_employees": "5"
    }
  ]
}
```

`annotation` carries the title, description, and type for every member in the
result. Use it to label output rather than hard-coding strings — it stays
correct when a description changes.

## Gotchas that cost time

Ten things, ordered by how likely each is to bite on day one.

1. **Numeric measures arrive as JSON strings.** `"900"`, not `900`. Every
   measure, including counts. Coerce at the parse boundary or a typed client
   will reject the payload.
1. **No `Bearer` prefix** on the `Authorization` header. The raw token is the
   whole value.
1. **A query requesting one field the caller cannot see fails entirely.** The
   response is an error, not a partial result with that column dropped. This is
   the behavior most likely to surprise you: a screen built and tested against a
   broadly-scoped user will error outright for a narrowly-scoped one. Design for
   it — either check members against the caller's tier before sending, or handle
   the failure per query and degrade the view.
1. **Dimension values can be `null`**, including on dimensions that look
   mandatory.
1. **The echoed `query` is normalized, not your input.** `dateRange` expands to
   full timestamps, `order` becomes an array, and `rowLimit` and `timezone` are
   added. Do not compare it against what you sent.
1. **Dropping a dimension re-aggregates — it does not hide a column.** Every
   measure is recomputed at whatever grain your dimensions define. Removing one
   changes what the number _means_, not just which columns return.
1. **A few measures are only meaningful within a scope.** `avg_scale_score` and
   `avg_percent_correct` pooled across incompatible assessment sources return a
   valid-looking, meaningless number **with no error**. Read the measure's own
   description before coarsening.
1. **Snapshot measures reject some granularities by design.** Weekly trends must
   group by `dates_school_week_start_date` rather than Cube's ISO
   `granularity: "week"`, because school weeks split at month and term
   boundaries.
1. **`count_students` on `student_enrollments_view` is seasonal.** It anchors to
   the current enrollment record, so it reads 0 outside the school year. Use
   `student_attendance_view.count_students` over a date range for a
   season-independent count.
1. **`staff_directory` always needs a date filter.** Without one, each
   employment period fans out to one row per calendar day in its range. Filter
   to a single day for a current roster.

## Sample queries

Values in responses are illustrative.

**Headcount by region, today.** Note `is_primary_position` to count each person
once, and `status_name` to exclude staff on leave.

```json
{
  "measures": ["staff_directory.count_employees"],
  "dimensions": ["staff_directory.regions_region_name"],
  "filters": [
    {
      "member": "staff_directory.is_primary_position",
      "operator": "equals",
      "values": ["true"]
    },
    {
      "member": "staff_directory.status_name",
      "operator": "equals",
      "values": ["Active"]
    }
  ],
  "timeDimensions": [
    {
      "dimension": "staff_directory.dates_date_day",
      "dateRange": ["2026-08-05", "2026-08-05"]
    }
  ]
}
```

**Attendance rate by school over a date range.**

```json
{
  "measures": ["student_attendance_view.avg_daily_attendance"],
  "dimensions": ["student_attendance_view.locations_abbreviation"],
  "timeDimensions": [
    {
      "dimension": "student_attendance_view.dates_date_day",
      "dateRange": ["2025-09-01", "2026-06-30"]
    }
  ],
  "order": { "student_attendance_view.avg_daily_attendance": "asc" }
}
```

**A weekly trend — note the school-week grouping**, per gotcha 8.

```json
{
  "measures": ["student_attendance_view.avg_daily_attendance"],
  "dimensions": ["student_attendance_view.dates_school_week_start_date"],
  "timeDimensions": [
    {
      "dimension": "student_attendance_view.dates_date_day",
      "dateRange": ["2025-09-01", "2025-12-19"]
    }
  ]
}
```

## Requesting something that is not here

If you need a view, dimension, or measure that does not exist, open a request
naming the grain you need, the dimensions and measures, any filters, and the
product surface consuming it. Our analytics engineers implement it in the
warehouse and the semantic layer, then regenerate this catalog.

Authorship stays on the KTAF side because data classification and grain
decisions live in the underlying warehouse models.

## Views

### student_attendance_view

Student attendance — row-level (one row per student × school day with attendance
recorded) and aggregate breakdowns in a single view. For ADA, use the
avg_daily_attendance measure rather than rebuilding the ratio from the raw
dimensions — it scopes both sides to full membership days with a recorded
attendance value, and a hand-rolled SUM(attendance_value) /
SUM(membership_value) counts days that were never recorded as absences. Never
average a per-row ratio either way. attendance_value (0.0–1.0) is the fractional
attendance contribution; membership_value (0.0–1.0) is the school's claim on the
student that day (split across schools if dual-enrolled); present_weight equals
attendance_value but tardies count 0.67. attendance_category is the coarse
rollup (Present, Absent, Tardy, In-School Suspension, Out-of-School Suspension);
attendance_code is the raw SIS code for specific drill-down. is_in_session and
is_membership_day come from school_calendars and are joined on (date_key,
student_school_enrollments.location_key). Contains direct student identifiers —
see access_policy for PII gating.

Query members as `student_attendance_view.<member>`; the table lists bare member
names.

#### Measures

| Member                               | Type   | Description                                                                                                                                                                        |
| ------------------------------------ | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `avg_daily_attendance`               | number | Average Daily Attendance (ADA) — attendance value summed over full membership days, divided by the count of those days.                                                            |
| `count_absent_days`                  | number | Total number of absence days (sum of is_absent).                                                                                                                                   |
| `count_chronically_absent`           | number | Students with cumulative ADA < 90% as of the snapshot date.                                                                                                                        |
| `count_chronically_absent_month_end` | number | Month-end chronic absence count — students with cumulative ADA < 90% as of the last school day of each calendar month.                                                             |
| `count_chronically_absent_week_end`  | number | Week-end chronic absence count — students with cumulative ADA < 90% as of the last school day of each PowerSchool school week.                                                     |
| `count_chronically_absent_year_end`  | number | Year-end chronic absence count — students with cumulative ADA < 90% at the final snapshot of each academic year (last school day for completed years, today for the current year). |
| `count_students`                     | number |                                                                                                                                                                                    |
| `count_truants`                      | number | Students meeting truancy criteria across the filtered period.                                                                                                                      |
| `count_truants_month_end`            | number | Month-end truancy count — students meeting truancy criteria as of the last school day of each calendar month.                                                                      |
| `count_truants_week_end`             | number | Week-end truancy count — students meeting truancy criteria as of the last school day of each PowerSchool school week.                                                              |
| `count_truants_year_end`             | number | Year-end truancy count — students meeting truancy criteria at the final snapshot of each academic year.                                                                            |
| `pct_chronically_absent`             | number | Chronic absence rate — count_chronically_absent / _count_ca_eligible_students.                                                                                                     |
| `pct_chronically_absent_month_end`   | number | Month-end chronic absence rate — count_chronically_absent_month_end / eligible students at month-end.                                                                              |
| `pct_chronically_absent_week_end`    | number | Week-end chronic absence rate — count_chronically_absent_week_end / eligible students at week-end. group by dates_school_week_start_date for week-over-week CA trends.             |
| `pct_chronically_absent_year_end`    | number | Year-end chronic absence rate — count_chronically_absent_year_end / eligible students at year-end.                                                                                 |
| `pct_ontime`                         | number | Percentage of present days where the student arrived on time (on-time days / present days).                                                                                        |
| `pct_tardy`                          | number | Percentage of present days where the student was tardy (tardy days / present days).                                                                                                |
| `pct_tier_1_2`                       | number | Percentage of CA-eligible students with cumulative ADA ≥ 90% (Tier 1 or Tier 2) as of the snapshot date.                                                                           |
| `pct_tier_1_2_month_end`             | number | Month-end percentage of CA-eligible students with cumulative ADA ≥ 90% (Tier 1 or Tier 2).                                                                                         |
| `pct_tier_1_2_week_end`              | number | Week-end percentage of CA-eligible students with cumulative ADA ≥ 90% (Tier 1 or Tier 2). group by dates_school_week_start_date.                                                   |
| `pct_tier_1_2_year_end`              | number | Year-end percentage of CA-eligible students with cumulative ADA ≥ 90% (Tier 1 or Tier 2).                                                                                          |
| `pct_tier_3`                         | number | Percentage of CA-eligible students with cumulative ADA 80–89% (Tier 3) as of the snapshot date.                                                                                    |
| `pct_tier_3_month_end`               | number | Month-end percentage of CA-eligible students with cumulative ADA 80–89% (Tier 3).                                                                                                  |
| `pct_tier_3_week_end`                | number | Week-end percentage of CA-eligible students with cumulative ADA 80–89% (Tier 3). group by dates_school_week_start_date.                                                            |
| `pct_tier_3_year_end`                | number | Year-end percentage of CA-eligible students with cumulative ADA 80–89% (Tier 3).                                                                                                   |
| `pct_truant`                         | number | Percentage of students meeting truancy criteria                                                                                                                                    |
| `pct_truant_month_end`               | number | Month-end truancy rate — count_truants_month_end / eligible students at month-end.                                                                                                 |
| `pct_truant_week_end`                | number | Week-end truancy rate — count_truants_week_end / eligible students at week-end. group by dates_school_week_start_date.                                                             |
| `pct_truant_year_end`                | number | Year-end truancy rate — count_truants_year_end / eligible students at year-end.                                                                                                    |

#### Dimensions

| Member                               | Type    | Description                                                                                                                                                                 |
| ------------------------------------ | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ada_tier`                           | string  | ADA tier based on cumulative attendance rate through this date.                                                                                                             |
| `attendance_category`                | string  | Coarse attendance category derived from the is_* flags with priority ordering (suspension > absent > tardy > present).                                                      |
| `attendance_code`                    | string  | Attendance identifier set by school.                                                                                                                                        |
| `attendance_date`                    | time    |                                                                                                                                                                             |
| `attendance_value`                   | number  | Daily attendance value — a real number, typically a fraction of 1 where 1 is a full attendance day.                                                                         |
| `birth_date`                         | time    |                                                                                                                                                                             |
| `dates_academic_year`                | number  | KIPP academic year (July start).                                                                                                                                            |
| `dates_academic_year_label`          | string  | Full span label for the academic year (e.g. "2025-2026" for the year beginning July 2025).                                                                                  |
| `dates_date_day`                     | time    | Timestamp cast of date_key.                                                                                                                                                 |
| `dates_day_of_week_name`             | string  | Full day name (Monday, Tuesday, etc.).                                                                                                                                      |
| `dates_is_weekday`                   | boolean | TRUE for Monday through Friday.                                                                                                                                             |
| `dates_month_name`                   | string  | Full month name (January, February, etc.).                                                                                                                                  |
| `dates_month_number`                 | number  | Month number (1-12).                                                                                                                                                        |
| `dates_quarter_number`               | number  | Calendar quarter (1-4).                                                                                                                                                     |
| `dates_school_week_start_date`       | time    |                                                                                                                                                                             |
| `enrollment_status`                  | string  | Current enrollment status of the student.                                                                                                                                   |
| `entry_date`                         | time    |                                                                                                                                                                             |
| `exit_date`                          | time    |                                                                                                                                                                             |
| `full_name`                          | string  | Student's full name in "Last, First, Mi." format.                                                                                                                           |
| `gender_identity`                    | string  | Self-identified gender for the student (e.g., M=Male F=Female).                                                                                                             |
| `grade_level`                        | number  | The grade the student is in.                                                                                                                                                |
| `graduation_year`                    | number  | Student graduation year.                                                                                                                                                    |
| `iep_classification`                 | string  | IEP placement classification for this enrollment stint (latest span).                                                                                                       |
| `is_absent`                          | number  | 1 if the student was absent, 0 if present.                                                                                                                                  |
| `is_chronically_absent`              | boolean | TRUE if the student's cumulative ADA through this date is below 90%.                                                                                                        |
| `is_ell`                             | boolean | TRUE if the student was classified as an English Language Learner during this enrollment stint.                                                                             |
| `is_gifted`                          | boolean | TRUE if the student has a gifted-and-talented identification on either the PowerSchool NJ extension or Miami user-fields extension.                                         |
| `is_iep`                             | boolean | TRUE if the student had an active Individualized Education Program during this enrollment stint.                                                                            |
| `is_iss`                             | number  | 1 if the student received in-school suspension on this date (S, ISS codes), 0 otherwise.                                                                                    |
| `is_latest_record`                   | boolean | TRUE on the most recent attendance row per student enrollment (partitioned by student × district × academic year × entry date).                                             |
| `is_meal_eligible`                   | boolean | TRUE if the student was eligible for free, reduced-price, or direct certification meals during this enrollment stint.                                                       |
| `is_month_end_record`                | boolean | TRUE on the last full membership day of each calendar month per student enrollment.                                                                                         |
| `is_ontime`                          | number  | 1 if the attendance code is not a T-prefix tardy code, 0 if tardy.                                                                                                          |
| `is_oss`                             | number  | 1 if the student received out-of-school suspension on this date (OS, OSS, OSSP, SHI codes), 0 otherwise.                                                                    |
| `is_retained_year`                   | boolean | TRUE if the student repeated this grade level in the same school compared to the prior academic year.                                                                       |
| `is_suspended`                       | number  | 1 if the student was suspended (any type) on this date.                                                                                                                     |
| `is_tardy`                           | number  | 1 if the student was tardy (T-prefix attendance code), 0 otherwise.                                                                                                         |
| `is_truant`                          | boolean | TRUE if the student meets regional truancy criteria.                                                                                                                        |
| `is_week_end_record`                 | boolean | TRUE on the last full membership day (membership_value = 1) of each PowerSchool school week per student enrollment.                                                         |
| `lea_student_identifier`             | number  | KIPP's own SIS identifier for the student.                                                                                                                                  |
| `locations_abbreviation`             | string  | Short display name for the location.                                                                                                                                        |
| `locations_campus`                   | string  | Physical campus name.                                                                                                                                                       |
| `locations_city`                     | string  | City.                                                                                                                                                                       |
| `locations_grade_band`               | string  | Grade band served (ES, MS, HS).                                                                                                                                             |
| `locations_location_name`            | string  | Canonical location name.                                                                                                                                                    |
| `locations_region_key`               | string  | Foreign key to regions.                                                                                                                                                     |
| `meal_eligibility`                   | string  | Meal eligibility category for this enrollment stint.                                                                                                                        |
| `membership_value`                   | number  | The amount of a student's membership this school claims. If a student attends more than one school each one will only be able to claim a certain portion of the membership. |
| `present_weight`                     | number  | Weighted presence value. 0.67 for tardy (T-prefix codes), otherwise equals attendance_value.                                                                                |
| `race`                               | string  | Racial category for the student.                                                                                                                                            |
| `regions_region_name`                | string  | Region name (Camden, Miami, Newark, Paterson, TAF).                                                                                                                         |
| `regions_state`                      | string  | US state (NJ or FL).                                                                                                                                                        |
| `school_calendars_is_in_session`     | boolean | TRUE if this date is an instructional day at this school.                                                                                                                   |
| `school_calendars_is_membership_day` | boolean | TRUE if this date counts toward student membership at this school.                                                                                                          |
| `special_education_code`             | string  | NJ state special education code (Newark and Camden only; NULL for Miami and Paterson).                                                                                      |
| `special_education_name`             | string  | Human-readable label for the NJ special education code (Newark and Camden only; NULL for Miami and Paterson).                                                               |
| `special_education_placement`        | string  | NJ special education placement category (Newark and Camden only; NULL for Miami and Paterson).                                                                              |
| `staff_homeroom_teacher_first_name`  | string  | Staff member's preferred first name.                                                                                                                                        |
| `staff_homeroom_teacher_full_name`   | string  | Staff member's preferred name in Last, First Middle format.                                                                                                                 |
| `staff_homeroom_teacher_last_name`   | string  | Staff member's preferred last name.                                                                                                                                         |
| `state_student_identifier`           | string  | The state-assigned student number for the student.                                                                                                                          |
| `student_enrollment_key`             | string  | Surrogate key derived from student_number, _dbt_source_project, academic_year, and entrydate.                                                                               |
| `student_key`                        | string  | Surrogate key derived from student_number.                                                                                                                                  |
| `terms_semester`                     | string  | Semester this period falls within.                                                                                                                                          |
| `terms_term_code`                    | string  | Short code for the period (e.g., Q1, Q2, PM1, Fall).                                                                                                                        |
| `terms_term_name`                    | string  | Display name for the period.                                                                                                                                                |
| `terms_term_type`                    | string  | Category of period (e.g., academic, PM, survey, assessment, fiscal).                                                                                                        |

Full descriptions for every member are in `reference/cube-catalog-meta.json`.

### student_enrollments_view

Point-in-time student enrollment — row-level (one row per enrolled student-day,
for roster exports and questions like "who was enrolled on October 1?"; pin a
single date by filtering dates_date_day) and aggregate headcount breakdowns in a
single view.

Query members as `student_enrollments_view.<member>`; the table lists bare
member names.

#### Measures

| Member           | Type   | Description                                |
| ---------------- | ------ | ------------------------------------------ |
| `count_students` | number | Distinct students enrolled, point-in-time. |

#### Dimensions

| Member                              | Type    | Description                                                                                                                         |
| ----------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `birth_date`                        | time    |                                                                                                                                     |
| `dates_academic_year`               | number  | KIPP academic year (July start).                                                                                                    |
| `dates_date_day`                    | time    | Timestamp cast of date_key.                                                                                                         |
| `dates_month_name`                  | string  | Full month name (January, February, etc.).                                                                                          |
| `dates_month_number`                | number  | Month number (1-12).                                                                                                                |
| `dates_quarter_number`              | number  | Calendar quarter (1-4).                                                                                                             |
| `dates_school_week_start_date`      | time    |                                                                                                                                     |
| `enrollment_status`                 | string  | Current enrollment status of the student.                                                                                           |
| `full_name`                         | string  | Student's full name in "Last, First, Mi." format.                                                                                   |
| `gender_identity`                   | string  | Self-identified gender for the student (e.g., M=Male F=Female).                                                                     |
| `grade_level`                       | number  | The grade the student is in.                                                                                                        |
| `graduation_year`                   | number  | Student graduation year.                                                                                                            |
| `iep_classification`                | string  | IEP placement classification for this enrollment stint (latest span).                                                               |
| `is_current_record`                 | boolean | TRUE on the school's latest attendance day that has occurred (per school × academic year, capped at today).                         |
| `is_ell`                            | boolean | TRUE if the student was classified as an English Language Learner during this enrollment stint.                                     |
| `is_gifted`                         | boolean | TRUE if the student has a gifted-and-talented identification on either the PowerSchool NJ extension or Miami user-fields extension. |
| `is_iep`                            | boolean | TRUE if the student had an active Individualized Education Program during this enrollment stint.                                    |
| `is_latest_record`                  | boolean | TRUE on the last attendance day of each enrollment stint.                                                                           |
| `is_meal_eligible`                  | boolean | TRUE if the student was eligible for free, reduced-price, or direct certification meals during this enrollment stint.               |
| `is_month_end_record`               | boolean | TRUE on the school's latest attendance day of each calendar month.                                                                  |
| `is_retained_year`                  | boolean | TRUE if the student repeated this grade level in the same school compared to the prior academic year.                               |
| `is_week_end_record`                | boolean | TRUE on the school's latest attendance day of each PowerSchool school week.                                                         |
| `lea_student_identifier`            | number  | KIPP's own SIS identifier for the student.                                                                                          |
| `locations_abbreviation`            | string  | Short display name for the location.                                                                                                |
| `locations_campus`                  | string  | Physical campus name.                                                                                                               |
| `locations_city`                    | string  | City.                                                                                                                               |
| `locations_grade_band`              | string  | Grade band served (ES, MS, HS).                                                                                                     |
| `locations_location_name`           | string  | Canonical location name.                                                                                                            |
| `locations_region_key`              | string  | Foreign key to regions.                                                                                                             |
| `meal_eligibility`                  | string  | Meal eligibility category for this enrollment stint.                                                                                |
| `race`                              | string  | Racial category for the student.                                                                                                    |
| `regions_region_name`               | string  | Region name (Camden, Miami, Newark, Paterson, TAF).                                                                                 |
| `regions_state`                     | string  | US state (NJ or FL).                                                                                                                |
| `special_education_code`            | string  | NJ state special education code (Newark and Camden only; NULL for Miami and Paterson).                                              |
| `special_education_name`            | string  | Human-readable label for the NJ special education code (Newark and Camden only; NULL for Miami and Paterson).                       |
| `special_education_placement`       | string  | NJ special education placement category (Newark and Camden only; NULL for Miami and Paterson).                                      |
| `staff_homeroom_teacher_first_name` | string  | Staff member's preferred first name.                                                                                                |
| `staff_homeroom_teacher_full_name`  | string  | Staff member's preferred name in Last, First Middle format.                                                                         |
| `staff_homeroom_teacher_last_name`  | string  | Staff member's preferred last name.                                                                                                 |
| `state_student_identifier`          | string  | The state-assigned student number for the student.                                                                                  |
| `student_attendance_daily_key`      | string  | Surrogate key derived from student_number, _dbt_source_project, and calendardate.                                                   |
| `student_enrollment_key`            | string  | FK to student_school_enrollments (the stint dimension).                                                                             |
| `student_key`                       | string  | Surrogate key derived from student_number.                                                                                          |

Full descriptions for every member are in `reference/cube-catalog-meta.json`.

### student_section_enrollments_view

Student section enrollments — row-level (one row per student x section
enrollment) and aggregate headcounts in a single view. Use for per-teacher class
rosters (filter to a lead teacher) and section drill-down. count_students is a
distinct-student headcount, correct per teacher — grouped by lead teacher it
answers "how many students does this teacher teach?". Contains direct student
identifiers — see access_policy for PII gating.

Query members as `student_section_enrollments_view.<member>`; the table lists
bare member names.

#### Measures

| Member           | Type   | Description                                                        |
| ---------------- | ------ | ------------------------------------------------------------------ |
| `count_students` | number | Distinct students with a section enrollment in the filtered slice. |

#### Dimensions

| Member                           | Type    | Description                                                                                                                         |
| -------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `academic_year`                  | number  | KIPP academic year (July start) the section enrollment falls in.                                                                    |
| `birth_date`                     | time    |                                                                                                                                     |
| `course_code`                    | string  | PowerSchool course number.                                                                                                          |
| `course_title`                   | string  | Course name.                                                                                                                        |
| `credit_type`                    | string  | Credit type for the course.                                                                                                         |
| `discipline`                     | string  | Course discipline from the course-subject crosswalk — broad grouping (ELA, Math, Science, Social Studies, CCR, World Language).     |
| `enrollment_status`              | string  | Current enrollment status of the student.                                                                                           |
| `entry_date`                     | time    | Date the student enrolled in this section.                                                                                          |
| `exit_date`                      | time    | Date the student left this section.                                                                                                 |
| `full_name`                      | string  | Student's full name in "Last, First, Mi." format.                                                                                   |
| `gender_identity`                | string  | Self-identified gender for the student (e.g., M=Male F=Female).                                                                     |
| `grade_level`                    | number  | The grade the student is in.                                                                                                        |
| `graduation_year`                | number  | Student graduation year.                                                                                                            |
| `identifier`                     | string  | Section number for this class.                                                                                                      |
| `is_current_section_enrollment`  | boolean | TRUE for the most-recent section enrollment among a student's sequential enrollments in the same course within an academic year.    |
| `is_dropped_course`              | boolean | TRUE if all enrollments for this student x course x year were dropped.                                                              |
| `is_dropped_section`             | boolean | TRUE if this section enrollment was dropped mid-term (negative section id + early exit).                                            |
| `is_foundations`                 | boolean | TRUE if this is a Foundations (intervention) course, per the course-subject crosswalk.                                              |
| `is_gifted`                      | boolean | TRUE if the student has a gifted-and-talented identification on either the PowerSchool NJ extension or Miami user-fields extension. |
| `is_homeroom`                    | boolean | TRUE when this is a homeroom section (HR course-number prefix).                                                                     |
| `is_retained_year`               | boolean | TRUE if the student repeated this grade level in the same school compared to the prior academic year.                               |
| `lea_student_identifier`         | number  | KIPP's own SIS identifier for the student.                                                                                          |
| `lead_teacher_staff_key`         | string  | FK to staff — the section's Lead Teacher.                                                                                           |
| `locations_abbreviation`         | string  | Short display name for the location.                                                                                                |
| `locations_campus`               | string  | Physical campus name.                                                                                                               |
| `locations_city`                 | string  | City.                                                                                                                               |
| `locations_grade_band`           | string  | Grade band served (ES, MS, HS).                                                                                                     |
| `locations_location_name`        | string  | Canonical location name.                                                                                                            |
| `locations_region_key`           | string  | Foreign key to regions.                                                                                                             |
| `period`                         | string  | Period expression encoding the days/periods the section meets (e.g., '1(A-F)').                                                     |
| `race`                           | string  | Racial category for the student.                                                                                                    |
| `regions_region_name`            | string  | Region name (Camden, Miami, Newark, Paterson, TAF).                                                                                 |
| `regions_state`                  | string  | US state (NJ or FL).                                                                                                                |
| `semester`                       | string  | Semester this period falls within.                                                                                                  |
| `staff_lead_teacher_first_name`  | string  | Staff member's preferred first name.                                                                                                |
| `staff_lead_teacher_full_name`   | string  | Staff member's preferred name in Last, First Middle format.                                                                         |
| `staff_lead_teacher_last_name`   | string  | Staff member's preferred last name.                                                                                                 |
| `state_student_identifier`       | string  | The state-assigned student number for the student.                                                                                  |
| `student_enrollment_key`         | string  | FK to student_school_enrollments (resolved school enrollment stint).                                                                |
| `student_key`                    | string  | Surrogate key derived from student_number.                                                                                          |
| `student_section_enrollment_key` | string  | Surrogate key (cc_dcid, _dbt_source_project).                                                                                       |
| `term_code`                      | string  | Short code for the period (e.g., Q1, Q2, PM1, Fall).                                                                                |
| `term_name`                      | string  | Display name for the period.                                                                                                        |
| `term_type`                      | string  | Category of period (e.g., academic, PM, survey, assessment, fiscal).                                                                |
| `year_in_network`                | number  | Count of years the student has been enrolled in the network.                                                                        |

Full descriptions for every member are in `reference/cube-catalog-meta.json`.

### student_assessment_scores_view

Assessment scores across internal Illuminate interims, NJ/FL state assessments,
and vendor benchmarks (i-Ready, DIBELS, STAR) — row-level (one row per student x
assessment x administration x response type) and aggregate breakdowns in a
single view. pct_proficient (mastery rate) is the source-agnostic headline;
scale_score is null for internal rows and percent_correct is null for state and
vendor rows. response_type / response_type_code carry the standard/skill
breakdown (Illuminate only). State and vendor administrations have no single
administered date, so the Date members (academic_year, academic_year_label,
date_day, month_number, month_name) resolve for every source but are scoped by
different dates per source: the administration date for Illuminate/college, the
student's completion (test) date for state/vendor. A cross-source date cut (e.g.
"scores in May") therefore mixes those two date concepts. Contains direct
student identifiers — see access_policy for PII gating.

Query members as `student_assessment_scores_view.<member>`; the table lists bare
member names.

#### Measures

| Member                     | Type   | Description                                                                                                                                                                                                                                         |
| -------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `avg_percent_correct`      | number | Grain: recomputes at any query grain, but meaningful only within a single subject/standard — pooling percent-correct across assessments is a silent-failure trap (numerically valid, semantically meaningless).                                     |
| `avg_scale_score`          | number | Grain: recomputes at any query grain, but meaningful only within a single assessment source/subject/grade — scale scores are not comparable across sources, so pooling them is a silent-failure trap (numerically valid, semantically meaningless). |
| `count_scores`             | number | Scored-response count.                                                                                                                                                                                                                              |
| `count_students`           | number | Distinct students (per student-year) with a score in the filtered slice.                                                                                                                                                                            |
| `pct_proficient`           | number | Proficiency/mastery rate — proficient scores / total scores.                                                                                                                                                                                        |
| `pct_proficient_crq`       | number | Proficiency rate for Constructed Response Questions (CRQ) across all regions.                                                                                                                                                                       |
| `pct_proficient_formative` | number | Proficiency rate across all formative module types (Quick Assessments, Multiple-Choice Quick Questions, and Constructed Response Questions).                                                                                                        |

#### Dimensions

| Member                           | Type    | Description                                                                                                                                                                                                                                                                                                                                                                                     |
| -------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `abbreviation`                   | string  | Short display name for the location.                                                                                                                                                                                                                                                                                                                                                            |
| `academic_subject`               | string  | Subject tested (e.g., Mathematics, English Language Arts, Reading, Science).                                                                                                                                                                                                                                                                                                                    |
| `academic_year`                  | number  | KIPP academic year (July start).                                                                                                                                                                                                                                                                                                                                                                |
| `academic_year_label`            | string  | Full span label for the academic year (e.g. "2025-2026" for the year beginning July 2025).                                                                                                                                                                                                                                                                                                      |
| `administration_period`          | string  | Scheduling period distinguishing administrations within an academic year.                                                                                                                                                                                                                                                                                                                       |
| `assessment_score_key`           | string  | Surrogate key.                                                                                                                                                                                                                                                                                                                                                                                  |
| `assessment_type`                | string  | Source-system category.                                                                                                                                                                                                                                                                                                                                                                         |
| `birth_date`                     | time    |                                                                                                                                                                                                                                                                                                                                                                                                 |
| `campus`                         | string  | Physical campus name.                                                                                                                                                                                                                                                                                                                                                                           |
| `category`                       | string  | Assessment category by format/content (e.g., CMA, CGI, NJSLA, FAST, SAT).                                                                                                                                                                                                                                                                                                                       |
| `city`                           | string  | City.                                                                                                                                                                                                                                                                                                                                                                                           |
| `course_code`                    | string  | PowerSchool course number.                                                                                                                                                                                                                                                                                                                                                                      |
| `course_title`                   | string  | Course name.                                                                                                                                                                                                                                                                                                                                                                                    |
| `credit_type`                    | string  | Credit type for the course.                                                                                                                                                                                                                                                                                                                                                                     |
| `date_day`                       | time    | Timestamp cast of date_key.                                                                                                                                                                                                                                                                                                                                                                     |
| `date_taken`                     | time    | Date the assessment was taken (completion date), as a standalone date dimension not joined to a calendar cube. date_taken is corrupt for a small share of internal rows, so calendar and academic-year rollups use the date_day / academic_year members instead (backed by assessment_date_key: the administration date for internal and college, the reliable test date for state and vendor). |
| `discipline`                     | string  | Course discipline from the course-subject crosswalk — broad grouping (ELA, Math, Science, Social Studies, CCR, World Language).                                                                                                                                                                                                                                                                 |
| `district_student_identifier`    | string  | Host public school district's identifier for the student.                                                                                                                                                                                                                                                                                                                                       |
| `enrollment_resolution`          | string  | How the section enrollment was resolved: subject_section or homeroom.                                                                                                                                                                                                                                                                                                                           |
| `enrollment_status`              | string  | Current enrollment status of the student.                                                                                                                                                                                                                                                                                                                                                       |
| `entry_date`                     | time    | Date the student enrolled in this section.                                                                                                                                                                                                                                                                                                                                                      |
| `exit_date`                      | time    | Date the student left this section.                                                                                                                                                                                                                                                                                                                                                             |
| `full_name`                      | string  | Student's full name in "Last, First, Mi." format.                                                                                                                                                                                                                                                                                                                                               |
| `gender_identity`                | string  | Self-identified gender for the student (e.g., M=Male F=Female).                                                                                                                                                                                                                                                                                                                                 |
| `grade_band`                     | string  | Grade band served (ES, MS, HS).                                                                                                                                                                                                                                                                                                                                                                 |
| `grade_level`                    | number  | The grade the student is in.                                                                                                                                                                                                                                                                                                                                                                    |
| `grade_level_tested`             | number  | Grade level the assessment targets.                                                                                                                                                                                                                                                                                                                                                             |
| `graduation_year`                | number  | Student graduation year.                                                                                                                                                                                                                                                                                                                                                                        |
| `identifier`                     | string  | Section number for this class.                                                                                                                                                                                                                                                                                                                                                                  |
| `iep_classification`             | string  | IEP placement classification for this enrollment stint (latest span).                                                                                                                                                                                                                                                                                                                           |
| `is_dropped_course`              | boolean | TRUE if all enrollments for this student x course x year were dropped.                                                                                                                                                                                                                                                                                                                          |
| `is_dropped_section`             | boolean | TRUE if this section enrollment was dropped mid-term (negative section id + early exit).                                                                                                                                                                                                                                                                                                        |
| `is_ell`                         | boolean | TRUE if the student was classified as an English Language Learner during this enrollment stint.                                                                                                                                                                                                                                                                                                 |
| `is_foundations`                 | boolean | TRUE if this is a Foundations (intervention) course, per the course-subject crosswalk.                                                                                                                                                                                                                                                                                                          |
| `is_gifted`                      | boolean | TRUE if the student has a gifted-and-talented identification on either the PowerSchool NJ extension or Miami user-fields extension.                                                                                                                                                                                                                                                             |
| `is_iep`                         | boolean | TRUE if the student had an active Individualized Education Program during this enrollment stint.                                                                                                                                                                                                                                                                                                |
| `is_internal_assessment`         | boolean | TRUE for KIPP-created internal assessments via Illuminate; FALSE for state and college.                                                                                                                                                                                                                                                                                                         |
| `is_mastery`                     | boolean | TRUE if the student met the mastery/proficiency threshold for this assessment.                                                                                                                                                                                                                                                                                                                  |
| `is_meal_eligible`               | boolean | TRUE if the student was eligible for free, reduced-price, or direct certification meals during this enrollment stint.                                                                                                                                                                                                                                                                           |
| `is_replacement`                 | boolean | Illuminate-only flag.                                                                                                                                                                                                                                                                                                                                                                           |
| `is_retained_year`               | boolean | TRUE if the student repeated this grade level in the same school compared to the prior academic year.                                                                                                                                                                                                                                                                                           |
| `lea_student_identifier`         | number  | KIPP's own SIS identifier for the student.                                                                                                                                                                                                                                                                                                                                                      |
| `lead_teacher_staff_key`         | string  | FK to staff — the section's Lead Teacher.                                                                                                                                                                                                                                                                                                                                                       |
| `location_name`                  | string  | Canonical location name.                                                                                                                                                                                                                                                                                                                                                                        |
| `meal_eligibility`               | string  | Meal eligibility category for this enrollment stint.                                                                                                                                                                                                                                                                                                                                            |
| `module_code`                    | string  | Module/test code identifying the assessment variant (e.g., QA1, ELA05, sat_total_score).                                                                                                                                                                                                                                                                                                        |
| `module_type`                    | string  | Module type for internal Illuminate assessments (e.g., QA, CR).                                                                                                                                                                                                                                                                                                                                 |
| `month_name`                     | string  | Full month name (January, February, etc.).                                                                                                                                                                                                                                                                                                                                                      |
| `month_number`                   | number  | Month number (1-12).                                                                                                                                                                                                                                                                                                                                                                            |
| `percent_correct`                | number  | Percent correct.                                                                                                                                                                                                                                                                                                                                                                                |
| `performance_band_label_number`  | number  | Numeric ordering of the performance band label within the band scale.                                                                                                                                                                                                                                                                                                                           |
| `period`                         | string  | Period expression encoding the days/periods the section meets (e.g., '1(A-F)').                                                                                                                                                                                                                                                                                                                 |
| `proficiency_level`              | string  | Proficiency band label (performance band for internal, achievement level for state).                                                                                                                                                                                                                                                                                                            |
| `race`                           | string  | Racial category for the student.                                                                                                                                                                                                                                                                                                                                                                |
| `region_key`                     | string  | Foreign key to regions.                                                                                                                                                                                                                                                                                                                                                                         |
| `region_name`                    | string  | Region name (Camden, Miami, Newark, Paterson, TAF).                                                                                                                                                                                                                                                                                                                                             |
| `response_type`                  | string  | Response-type breakdown (e.g., overall, strand, standard).                                                                                                                                                                                                                                                                                                                                      |
| `response_type_code`             | string  | Short code identifying the response type.                                                                                                                                                                                                                                                                                                                                                       |
| `response_type_description`      | string  | Human-readable response-type description.                                                                                                                                                                                                                                                                                                                                                       |
| `response_type_root_description` | string  | Description of the root (top-level) response type.                                                                                                                                                                                                                                                                                                                                              |
| `salesforce_contact_id`          | string  | KIPPADB (Salesforce) contact identifier for the student.                                                                                                                                                                                                                                                                                                                                        |
| `scale_score`                    | number  | Scale score achieved.                                                                                                                                                                                                                                                                                                                                                                           |
| `scope`                          | string  | How scores link to students: enrollment (tied to a section enrollment) or student.                                                                                                                                                                                                                                                                                                              |
| `semester`                       | string  | Semester this period falls within.                                                                                                                                                                                                                                                                                                                                                              |
| `source_assessment_id`           | number  | Illuminate assessment id carried to the administration grain (the canonical id).                                                                                                                                                                                                                                                                                                                |
| `special_education_code`         | string  | NJ state special education code (Newark and Camden only; NULL for Miami and Paterson).                                                                                                                                                                                                                                                                                                          |
| `special_education_name`         | string  | Human-readable label for the NJ special education code (Newark and Camden only; NULL for Miami and Paterson).                                                                                                                                                                                                                                                                                   |
| `special_education_placement`    | string  | NJ special education placement category (Newark and Camden only; NULL for Miami and Paterson).                                                                                                                                                                                                                                                                                                  |
| `staff_lead_teacher_first_name`  | string  | Staff member's preferred first name.                                                                                                                                                                                                                                                                                                                                                            |
| `staff_lead_teacher_full_name`   | string  | Staff member's preferred name in Last, First Middle format.                                                                                                                                                                                                                                                                                                                                     |
| `staff_lead_teacher_last_name`   | string  | Staff member's preferred last name.                                                                                                                                                                                                                                                                                                                                                             |
| `state`                          | string  | US state (NJ or FL).                                                                                                                                                                                                                                                                                                                                                                            |
| `state_student_identifier`       | string  | The state-assigned student number for the student.                                                                                                                                                                                                                                                                                                                                              |
| `student_enrollment_key`         | string  | FK to student_school_enrollments (resolved school enrollment stint).                                                                                                                                                                                                                                                                                                                            |
| `student_key`                    | string  | Surrogate key derived from student_number.                                                                                                                                                                                                                                                                                                                                                      |
| `student_section_enrollment_key` | string  | Surrogate key (cc_dcid, _dbt_source_project).                                                                                                                                                                                                                                                                                                                                                   |
| `term_code`                      | string  | Short code for the period (e.g., Q1, Q2, PM1, Fall).                                                                                                                                                                                                                                                                                                                                            |
| `term_name`                      | string  | Display name for the period.                                                                                                                                                                                                                                                                                                                                                                    |
| `term_type`                      | string  | Category of period (e.g., academic, PM, survey, assessment, fiscal).                                                                                                                                                                                                                                                                                                                            |
| `test_type`                      | string  | Official vs Practice for college-entrance administrations.                                                                                                                                                                                                                                                                                                                                      |
| `title`                          | string  | Display name of the assessment.                                                                                                                                                                                                                                                                                                                                                                 |
| `year_in_network`                | number  | Count of years the student has been enrolled in the network.                                                                                                                                                                                                                                                                                                                                    |

Full descriptions for every member are in `reference/cube-catalog-meta.json`.

### staff_directory

Open staff directory — roster, employment history, and work-contact info. One
row per employee x employment period — a contiguous window during which status,
job, worker type, org unit, and location all held simultaneously — with
point-in-time manager context. Use for the staff roster, drill-down, and
individual investigations. Contains no personal or sensitive data (personal
contact, DOB, demographics) — see staff_pii for those fields.

Query members as `staff_directory.<member>`; the table lists bare member names.

#### Measures

| Member            | Type   | Description                  |
| ----------------- | ------ | ---------------------------- |
| `count_employees` | number | Distinct employees in scope. |

#### Dimensions

| Member                      | Type    | Description                                                                                                                                                      |
| --------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `active_directory_username` | string  | Staff member's Active Directory username (lowercased), used as a cross-system identifier.                                                                        |
| `business_unit_name`        | string  | Display name for the home Business Unit, coalesced from longName and shortName of the ADP nameCode where typeCode = 'Business Unit', as held during this period. |
| `dates_academic_year`       | number  | KIPP academic year (July start).                                                                                                                                 |
| `dates_date_day`            | time    | Timestamp cast of date_key.                                                                                                                                      |
| `dates_month_name`          | string  | Full month name (January, February, etc.).                                                                                                                       |
| `dates_month_number`        | number  | Month number (1-12).                                                                                                                                             |
| `dates_year_number`         | number  | Calendar year.                                                                                                                                                   |
| `department_group`          | string  | Broad department grouping for the staff member's current role (e.g. Academics, Ops).                                                                             |
| `department_name`           | string  | Display name for the home Department, coalesced from longName and shortName of the ADP nameCode where typeCode = 'Department', as held during this period.       |
| `effective_start_date`      | time    | Start of the contiguous period (intersection of all SCD2 children).                                                                                              |
| `first_name`                | string  | Staff member's preferred first name.                                                                                                                             |
| `full_name`                 | string  | Staff member's preferred name in Last, First Middle format.                                                                                                      |
| `full_time_equivalency`     | number  | FTE ratio for this work assignment. 1.0 represents full-time; fractional values represent part-time assignments.                                                 |
| `google_email`              | string  | Staff member's Google Workspace email address from LDAP.                                                                                                         |
| `is_management_position`    | boolean | TRUE if this work assignment is designated as a management position.                                                                                             |
| `is_primary_position`       | boolean | TRUE if this was the worker's primary work assignment during the period.                                                                                         |
| `job_code`                  | string  | Job code value for the work assignment, as held during this period.                                                                                              |
| `job_function_code`         | string  | Short code for the staff member's current job function category (e.g. TEACH, TIR).                                                                               |
| `job_function_level`        | number  | Numeric seniority level for the staff member's current job function (higher = more senior).                                                                      |
| `last_name`                 | string  | Staff member's preferred last name.                                                                                                                              |
| `locations_abbreviation`    | string  | Short display name for the location.                                                                                                                             |
| `locations_campus`          | string  | Physical campus name.                                                                                                                                            |
| `locations_city`            | string  | City.                                                                                                                                                            |
| `locations_grade_band`      | string  | Grade band served (ES, MS, HS).                                                                                                                                  |
| `locations_location_name`   | string  | Canonical location name.                                                                                                                                         |
| `original_hire_date`        | time    | The date the staff member was originally hired at KIPP, from worker_dates in ADP.                                                                                |
| `position_title`            | string  | Free-text position title for the work assignment, as held during this period.                                                                                    |
| `regions_region_name`       | string  | Region name (Camden, Miami, Newark, Paterson, TAF).                                                                                                              |
| `regions_state`             | string  | US state (NJ or FL).                                                                                                                                             |
| `rehire_date`               | time    | The most recent rehire date for the staff member, if rehired, from worker_dates in ADP.                                                                          |
| `staff_key`                 | string  | Surrogate key derived from employee_number.                                                                                                                      |
| `staff_manager_first_name`  | string  | Staff member's preferred first name.                                                                                                                             |
| `staff_manager_full_name`   | string  | Staff member's preferred name in Last, First Middle format.                                                                                                      |
| `staff_manager_last_name`   | string  | Staff member's preferred last name.                                                                                                                              |
| `staff_manager_staff_key`   | string  | Surrogate key derived from employee_number.                                                                                                                      |
| `staff_manager_work_email`  | string  | Staff member's work email address from ADP.                                                                                                                      |
| `staff_unique_id`           | number  | KIPP-assigned unique identifier for all staff members across all entities.                                                                                       |
| `status_name`               | string  | Assignment-level employment status during this period (Active, Leave, Terminated).                                                                               |
| `status_reason`             | string  | Reason for the current status (e.g., leave type — Medical, Family, Disability; or termination reason — Resignation, Non-Renewal).                                |
| `work_email`                | string  | Staff member's work email address from ADP.                                                                                                                      |
| `worker_type`               | string  | Display name for the ADP worker type (e.g., Regular, Temporary), as held during this period.                                                                     |

Full descriptions for every member are in `reference/cube-catalog-meta.json`.

### staff_pii

!!! warning "Gated — not available to external integrations"

    This view holds sensitive personal fields and is access-gated per viewer. It
    is listed here so you can see it exists and is not part of your scope. Do not
    design against it.

Sensitive staff PII — personal contact info, date of birth, and demographics —
split out of the open staff directory (see staff_directory). One row per
employee x employment period; always apply a date filter or each period fans out
to one row per calendar day in its effective range. Filter is_primary_position =
true and status_name = 'Active' to see each current employee once.

Query members as `staff_pii.<member>`; the table lists bare member names.

#### Measures

| Member            | Type   | Description                  |
| ----------------- | ------ | ---------------------------- |
| `count_employees` | number | Distinct employees in scope. |

#### Dimensions

| Member                   | Type    | Description                                                                                                             |
| ------------------------ | ------- | ----------------------------------------------------------------------------------------------------------------------- |
| `birth_date`             | time    | Staff member's date of birth.                                                                                           |
| `dates_academic_year`    | number  | KIPP academic year (July start).                                                                                        |
| `dates_date_day`         | time    | Timestamp cast of date_key.                                                                                             |
| `department_group`       | string  | Broad department grouping for the staff member's current role (e.g. Academics, Ops).                                    |
| `full_name`              | string  | Staff member's preferred name in Last, First Middle format.                                                             |
| `gender_identity`        | string  | Staff member's preferred gender identity as reported in the staff information survey, with ADP gender_code as fallback. |
| `is_hispanic`            | boolean | TRUE if the staff member identified as Hispanic/Latino/Latinx in the staff information survey or ADP ethnicity record.  |
| `is_primary_position`    | boolean | TRUE if this was the worker's primary work assignment during the period.                                                |
| `job_function_code`      | string  | Short code for the staff member's current job function category (e.g. TEACH, TIR).                                      |
| `job_function_level`     | number  | Numeric seniority level for the staff member's current job function (higher = more senior).                             |
| `locations_abbreviation` | string  | Short display name for the location.                                                                                    |
| `locations_region_key`   | string  | Foreign key to regions.                                                                                                 |
| `personal_cell_phone`    | string  | Staff member's personal cell phone number from ADP.                                                                     |
| `personal_email`         | string  | Staff member's personal email address from ADP.                                                                         |
| `race`                   | string  | Staff member's racial category for reporting purposes, sourced from the staff information survey with ADP as fallback.  |
| `staff_key`              | string  | Surrogate key derived from employee_number.                                                                             |
| `status_name`            | string  | Assignment-level employment status during this period (Active, Leave, Terminated).                                      |

Full descriptions for every member are in `reference/cube-catalog-meta.json`.
