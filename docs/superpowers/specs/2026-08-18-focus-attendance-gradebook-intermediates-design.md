# Focus attendance and gradebook intermediate models — design

Design for the three remaining Focus intermediate models tracked in
[#4865](https://github.com/TEAMSchools/teamster/issues/4865):
`int_focus__attendance_day`, `int_focus__attendance_period`, and
`int_focus__gradebook_grades`.

Refs #3584, #4865, #4803

## Summary

All three models resolve reference tables that the staging layer deliberately
leaves unresolved. None of them is the `int_focus__{entity}` decode pattern —
none of the three source tables carries a `custom_*` column, so there are no
labels to decode and no `__pivot` models are created.

The gradebook model additionally requires **new dlt ingestion**. The tables that
link a gradebook assignment to a course period exist in Focus but were never
configured for extraction. This was not known when #4865 was written.

## What changed from the issue's assumptions

Every claim below was measured against live data on 2026-08-18, either in
`dagster_kippmiami_dlt_focus` or by probing the Focus Postgres directly from a
`kippmiami` code-server pod.

### `attendance_day.daily_code` is a short name, not an id

The issue assumed the attendance code columns resolve the same way on both
tables. They do not.

| Column                                      | Resolves to                   | Orphans        |
| ------------------------------------------- | ----------------------------- | -------------- |
| `attendance_period.attendance_code`         | `attendance_codes.id`         | 0 of 15,171    |
| `attendance_period.attendance_teacher_code` | `attendance_codes.id`         | 0 of 15,171    |
| `attendance_day.daily_code`                 | `attendance_codes.short_name` | 0 of 895 coded |

`attendance_day` holds `NULL`, `U`, `AE`, or `AD` — short names, not ids. Codes
are scoped per school per year, and `attendance_day` carries no `school_id`, so
the join needs school resolved from `marking_periods` first. With that scoping
all 895 coded rows resolve.

`daily_pres_code` is null on every row.

### `state_value` is already the present/absent classification

6,804 of 7,699 day rows are `daily_code is null` with `state_value = 1`; the
remaining 895 are `state_value = 0` with a code. The codes join adds the reason
for an absence (excused, documented, unexcused) and its title. It does not
supply the base classification, which `state_value` already carries.

Tardies do not appear at day grain. `T` exists only as a period-level code.

### The gradebook-to-course link exists but is not ingested

The ERD names these only as a glob, `gradebook_*_join_course_periods`
(`docs/superpowers/specs/references/focus-db-erd.md`). Probing Focus Postgres
resolved the glob to three tables, two of which matter:

| Table                                            | Carries                                                                                                    |
| ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| `gradebook_assignments_join_course_periods`      | `assignment_id`, `course_period_id`, `marking_period_id`, `due_date`, `assigned_date`, `publish_date`      |
| `gradebook_assignment_types_join_course_periods` | `assignment_type_id`, `course_period_id`, `marking_period_id`, `final_grade_percent`, `drop_lowest_grades` |

Both carry `updated_at :: timestamp with time zone`, so both take
`cursor_column: updated_at`, matching 75 of the 76 existing `focus.yaml`
entries.

The third, `gradebook_deleted_assignments_join_course_periods`, holds deleted
rows and `jsonb` blobs. Out of scope. Also out of scope are the backup artifacts
returned by the same probe: `gradebook_assignments_asn_20160323`,
`gradebook_assignments_aug5`, and the `*_restoration_donotdelete` pair.

The type link is the more valuable of the two. 87,913 of its 89,206 rows carry
`final_grade_percent` — category weights, keyed per course period. Without them
a gradebook category is a bare label.

### A grade's course period is ambiguous and must be disambiguated

An assignment maps to many course periods, because a teacher assigns the same
work across sections. `gradebook_grades` names only `student_id` and
`assignment_id`.

| Measure                                                  | Value             |
| -------------------------------------------------------- | ----------------- |
| Link rows / distinct assignments                         | 428,009 / 355,583 |
| Assignments mapped to more than one course period        | 28,074            |
| Graded assignments mapped to more than one course period | 11 of 12          |
| Grades whose assignment has no link row                  | 30                |

A direct join to the link table would multiply nearly every grade. Filtering to
the course period the student is scheduled into resolves it: every one of the
653 grades then lands on exactly one course period, and zero grades with a link
row fail to resolve.

### Two fan-out hazards on the supporting joins

Both were measured, and both shape the SQL rather than being left to a test.

`schedule` repeats a student and course-period pair on 299 combinations. The
disambiguation check above counted _distinct course periods_, so it could not
see this — a grade matching two schedule rows for one section still reads as
one. The schedule is therefore used as a grain-collapsed lookup, never joined as
a table.

`gradebook_assignment_types_join_course_periods` repeats an `assignment_type_id`
and `course_period_id` pair on 23,318 combinations, almost certainly once per
marking period, since category weights change by quarter. The weight join
therefore keys on the triple including `marking_period_id`, which the assignment
link row supplies.

The assignment link itself has zero duplicate
`(assignment_id, course_period_id)` pairs.

## Scope

### Ingestion

Two entries added to
`src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml`, each with
`cursor_column: updated_at`:

- `gradebook_assignments_join_course_periods`
- `gradebook_assignment_types_join_course_periods`

### Staging

Two contract-enforced models in `src/dbt/focus/models/staging/`, PK `id`,
projecting only populated columns. Neither source table has a `deleted` column,
so neither gets a soft-delete filter.

- `stg_focus__gradebook_assignments_join_course_periods`
- `stg_focus__gradebook_assignment_types_join_course_periods`

### Intermediate

Three models in `src/dbt/focus/models/intermediate/`. No `__pivot` models.

## Model designs

### `int_focus__attendance_day`

Grain: student by school date. PK `student_attendance_day_id`, 7,699 rows, no
duplicates.

Staging columns carry through with the established renames — `syear` becomes
`academic_year`, `school_id` becomes `schoolid` — matching `int_focus__schedule`
and `int_focus__report_card_grades`.

Joins:

- Left join `stg_focus__marking_periods` on `marking_period_id`, supplying
  `schoolid` and the marking-period attributes. Left, not inner: three rows hold
  an unresolvable `marking_period_id` and must not drop.
- Left join `stg_focus__attendance_codes` on `academic_year`, `schoolid`, and
  `short_name = daily_code`, exposing `daily_code_title`, `daily_code_excused`,
  `daily_code_tardy`, and `daily_code_state_code`.

`state_value` carries through as the present flag.

### `int_focus__attendance_period`

Grain: student by school date by course period. PK
`student_attendance_period_id`, 15,171 rows, no duplicates.

Joins:

- Two left joins to `stg_focus__attendance_codes` on `id`, exposing
  `attendance_code_*` from `attendance_code` and `attendance_teacher_code_*`
  from `attendance_teacher_code`. Zero orphans on both.
- Left join `stg_focus__marking_periods` for `schoolid`, mirroring the day
  model.

No course-period join. `int_focus__schedule` already resolves course period,
course, and teacher from `course_period_id`; duplicating that here would mean
two models to change when the resolution changes. This model exposes
`course_period_id` and consumers join `int_focus__schedule`.

### `int_focus__gradebook_grades`

Grain: one row per `gradebook_grades.id`. PK `student_gradebook_grade_id`.

A `student_course_periods` CTE selects `student_id` and `course_period_id` from
`stg_focus__schedule` with `group by 1, 2`. The `group by` collapses the 299
repeated pairs and states the intended grain explicitly. It reads staging rather
than `int_focus__schedule` so it does not inherit that model's inner joins to
`course_periods` and `courses`.

Joins, all left, so the 30 grades without a link row keep their score and carry
a null course period rather than disappearing:

- `stg_focus__gradebook_assignments_join_course_periods` on `assignment_id`,
  restricted to course periods present in `student_course_periods`, supplying
  `course_period_id`, `marking_period_id`, `due_date`, `assigned_date`, and
  `publish_date`.
- `stg_focus__gradebook_assignments` on `assignment_id`, supplying the
  assignment title, points, and `exclude_from_average`.
- `stg_focus__gradebook_assignment_types` on `assignment_type_id`, supplying the
  category title.
- `stg_focus__gradebook_assignment_types_join_course_periods` on the triple
  `assignment_type_id`, `course_period_id`, `marking_period_id`, supplying
  `final_grade_percent` and `drop_lowest_grades`.

## Testing

Each model carries `unique` and `not_null` on its primary key, declared at
`severity: error` to match the surrounding staging models.

**That declaration does not take effect, and the tests run at `warn`.** The root
project sets `data_tests: +severity: warn` in
`src/dbt/kippmiami/dbt_project.yml`, and root-project config outranks config
declared inside an installed package — which every `focus` model is. The
manifest confirms it: existing tests such as
`unique_stg_focus__attendance_codes_id` resolve to `warn` despite their YAML
declaring `error`.

So a join that multiplied rows would warn, not fail. The PK tests are a signal,
not a gate. Grain was therefore confirmed directly rather than inferred from a
green build — `count(*)` against `count(distinct <pk>)` on each built model:

| Model                                                  | Rows    | Distinct PK |
| ------------------------------------------------------ | ------- | ----------- |
| `int_focus__attendance_day`                            | 7,701   | 7,701       |
| `int_focus__attendance_period`                         | 15,633  | 15,633      |
| `stg_focus__gradebook_assignments_join_course_periods` | 428,025 | 428,025     |

Run that check on `int_focus__gradebook_grades` too before merging. Whether the
repo wants `+severity: warn` overridden for primary-key tests is a network-wide
policy question, out of scope here.

## Sequencing

One branch, one PR, two pushes. The dlt load runs in the PR's Dagster branch
deployment, so dbt Cloud CI validates the new dbt models against real rows
before merge.

This works because the destination dataset is derived from the code location
alone — `dagster_{code_location}_dlt_focus` in
`src/teamster/libraries/dlt/focus/assets.py` — with no deployment segment. A
branch-deployment load therefore lands in `dagster_kippmiami_dlt_focus`, the
same dataset prod uses, which Focus sources read in every dbt target.

1. Push the `focus.yaml` change alone. The path is in the trigger list for
   `.github/workflows/deploy-prod-kippmiami.yaml`, which fires on
   `pull_request`, so the branch deployment builds itself.
1. Launch the two new dlt assets in the branch deployment. The `@dlt_assets` op
   runs over a source narrowed to the run's asset selection, so only these two
   tables load, not all 78.
1. Verify in BigQuery that the type-link triple is unique before finalizing the
   intermediate.
1. Push the two staging models and all three intermediates. dbt Cloud CI
   validates against loaded rows.

Splitting the pushes is deliberate. Sending everything at once means dbt CI runs
before the tables exist and fails on missing sources for no useful reason.

### Two accepted consequences

The branch-deployment load writes into the **production** landing dataset. It is
additive — two new tables nothing reads yet — but it is not sandboxed and it
happens before merge.

dlt persists each table's probe signature with the load, keyed on the shared
`focus` schema. After merge, prod's first probe tick sees no drift on these two
tables and skips them. That is correct behavior, not a failure, but it will read
as a skip in the run log.

## Out of scope

**No `attendance_calendar` join.** The issue asks for one, to distinguish a
non-attendance day from a missing record. Two reasons not to build it.

The information is not there. `attendance_calendar.minutes` is `999` on all
7,697 matched 2026 rows — a single sentinel, not real expected minutes, so there
is nothing to compare `minutes_present` against. `bell_schedule_id` is populated
on 544 rows, seven percent.

The missing-record case is not visible at this grain. A row that exists is a day
that happened. Detecting _absent_ rows requires a scaffold of enrolled students
crossed with calendar days, which is a different grain and belongs to the
consuming mart, where enrollment is already in hand.

Recorded for future reference: joining the calendar is safe when it is wanted.
Scoping to `attendance_calendars.default_calendar = 'Y'`, the idiom
`int_focus__school_year_first_day` already uses, reduces 1,554 duplicate
`(syear, school_id, school_date)` keys to 177, all in `syear` 2016. For 2026 the
join is one-to-one, with no need to route through `student_enrollment`.

**No re-keying of orphaned AY2025 Miami attendance.** #4803 records 155,863 rows
orphaned from `dim_student_enrollments` after the Focus cutover. Focus carries
AY2026-27 forward only, so these models give Miami a correct current year and
leave that historical leg unanswered. #4803 still needs a separate answer for
it.

**No `__pivot` models.** None of the three source tables has a `custom_*`
column, so there is nothing to decode.

## Follow-up

#4865's body needs rewriting. It states that all three models need no new
ingestion and that staging coverage is the only gate. That is true for the two
attendance models and wrong for the gradebook model.
