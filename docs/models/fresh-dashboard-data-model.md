# FRESH Dashboard Data Model

## What is FRESH?

FRESH is the network's enrollment recruitment dashboard. It tracks progress
against recruitment targets (seats, new students, and the inquiry, application,
offer and enrollment funnel) by region, school and grade. The Student
Recruitment and Enrollment team (SRE) and school operations teams use it to see
where each school stands against its goals and which student records need
cleanup.

- Owner: the data team, with Anthony Walters as owner.
- Stakeholder: Maria-Cristina Ventresca, Managing Director, Marketing, Comms,
  and Enrollment.
- Targets: owned by SRE. SRE's own workbook is hand-maintained; the Finalsite
  goals Google Sheet is the copy dbt reads.

The Tableau workbook has four tabs: **Landing Page** (the default view),
**Progress to Goals**, **School Ops Team** and **SRE Team**. It reads three
reporting models, all in the `fresh_dashboard` exposure:

- `rpt_tableau__fresh_dashboard_progress_to_goals`: enrolled students against
  enrollment targets.
- `rpt_tableau__fresh_dashboard_aggregated`: funnel counts against funnel goals.
- `rpt_tableau__fresh_dashboard_qc`: a worklist of students whose Finalsite
  record disagrees with the SIS.

The exposure also reads `int_tableau__finalsite_student_scaffold` directly (see
_Known issues, need to fix_). Which tab reads which data source, and who opens
each tab, is an open question (see _Open questions_).

## Data model overview

```text
1. THE SPINE (one row per school x grade)

  stg_powerschool__schools ─────────────┐
  stg_powerschool__students ────────────┤
  int_focus__schools ───────────────────┤
  int_focus__student_enrollment_roster ─┼─▶ int_tableau__fresh_enrollment_scaffold
  stg_google_sheets__people__locations ─┤
  int_finalsite__status_report_unpivot ─┘   (net-new schools/grades only)

2. THE GOALS (numeric targets)

  stg_google_sheets__finalsite__goals ─┬─▶ int_tableau__fresh_goals_scaffold
                                       │     (funnel goals, inner-joined to the spine)
                                       └─▶ int_google_sheets__finalsite__goals_pivot
                                             (the five Enrollment targets as columns;
                                              consumers filter goal_type)

3. THE ACTUALS (where students are in the funnel)

  stg_finalsite__status_report ─▶ int_finalsite__status_report_unpivot ────────┐
  stg_google_sheets__finalsite__status_crosswalk                              │
    └─▶ int_google_sheets__finalsite__status_crosswalk_unpivot ───────────────┤
  int_extracts__student_enrollments (NJ regions; SIS side) ───────────────────┼─▶ int_tableau__finalsite_student_scaffold
  int_focus__student_enrollment_roster (Miami; SIS side) ─────────────────────┤
  int_finalsite__contact_id_attributes (Focus <-> Finalsite id bridge) ───────┘

4. THE CONSUMERS (the fresh_dashboard exposure)

  int_tableau__fresh_enrollment_scaffold ────┐
  int_google_sheets__finalsite__goals_pivot ─┤
  int_people__location_crosswalk ────────────┼─▶ rpt_tableau__fresh_dashboard_progress_to_goals
  int_tableau__finalsite_student_scaffold ───┘

  int_tableau__fresh_goals_scaffold ─────────┐
  int_tableau__finalsite_student_scaffold ───┴─▶ rpt_tableau__fresh_dashboard_aggregated

  int_tableau__finalsite_student_scaffold ───┐
  int_extracts__student_enrollments ─────────┤
  int_finalsite__contact_id_attributes ──────┼─▶ rpt_tableau__fresh_dashboard_qc
  stg_finalsite__status_report ──────────────┘

  int_tableau__finalsite_student_scaffold ─────▶ fresh_dashboard (read directly)
```

The spine and the goals are two independent inputs joined together. The actuals
come from a separate Finalsite pipeline and join in at the reporting layer.

## Terms

| term                               | meaning                                                                                                                                                    |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SRE                                | Student Recruitment and Enrollment, the team that owns recruitment targets and Finalsite data entry.                                                       |
| Spine / scaffold                   | `int_tableau__fresh_enrollment_scaffold`: one row per school and grade being reported on, so the dashboard has a row even where no student or goal exists. |
| Recruitment year                   | The `finalsite_recruitment_year` dbt var: the Finalsite cycle FRESH reports on. Start-year form (AY2026-2027 = `2026`).                                    |
| `grade_level = -9`                 | A whole-school total row. A reporting convention, not a SIS grade.                                                                                         |
| `grade_level = -1`                 | Pre-K (K is `0`, grades 1-12 are `1`-`12`).                                                                                                                |
| `schoolid = 0`                     | A region rollup row (spine and goals) or a Finalsite record with no assigned school yet (actuals, `school = 'No School Assigned'`).                        |
| `goal_granularity`                 | `School` (`grade_level = -9`), `School/Grade Level`, or `Region/Grade Level` (`schoolid = 0`).                                                             |
| `goal_type` / `goal_name`          | The goal family and the specific goal. Funnel goal names come from the status crosswalk; Enrollment goal names are typed into the goals sheet.             |
| `grouped_status`                   | The funnel stage a Finalsite status maps to, from the crosswalk's `status_group_value`.                                                                    |
| `grouped_status_timeframe`         | `Ever` counts a student who ever reached the stage; `Current` counts only a student whose latest status is in the stage.                                   |
| `latest_status`                    | A student's most recent Finalsite status: latest status date, ties broken by `status_order` (highest wins).                                                |
| `status_order`                     | A hardcoded rank per Finalsite status field in `int_finalsite__status_report_unpivot`, mirroring the crosswalk's `detailed_status_ranking`.                |
| `enrollment_type`                  | `New` or `Returning`, from Finalsite. `aligned_enrollment_type` is the constant `All`, used to add New and Returning together.                             |
| `enroll_status`                    | The SIS enrollment code: `0` enrolled, `2` withdrawn, `3` graduated, `-1` pre-registered. `1` is treated as invalid in this repo.                          |
| `finalsite_expected_enroll_status` | What the SIS should show if Finalsite is right: `0`, `2` or NULL. See _How Finalsite's `latest_status` becomes an expected enrollment status_.             |
| Persistence                        | A current student returning next year (`Re-Enroll Projection`). "Retention" means grade repetition in this network, a different thing.                     |
| Reset Protocol                     | SRE's fix for a same-day status tie: move the student to another status, wait a day, then set the status you want.                                         |

## Where the data comes from

| source                                                     | reaches FRESH through                                                                        | owner                                         |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------------------- | --------------------------------------------- |
| Finalsite status report (SFTP file drop, all four regions) | `stg_finalsite__status_report` → `int_finalsite__status_report_unpivot`                      | SRE enters the data; data team owns ingestion |
| Finalsite contact ids                                      | `int_finalsite__contact_id_attributes` (bridges Focus ids to Finalsite ids)                  | data team                                     |
| PowerSchool (Newark, Camden, Paterson)                     | `stg_powerschool__schools`, `stg_powerschool__students`, `int_extracts__student_enrollments` | school operations enter; data team ingests    |
| Focus (Miami)                                              | `int_focus__schools`, `int_focus__student_enrollment_roster`                                 | school operations enter; data team ingests    |
| Finalsite goals Google Sheet                               | `stg_google_sheets__finalsite__goals`                                                        | SRE supplies values; data team pastes them    |
| Finalsite status crosswalk Google Sheet                    | `stg_google_sheets__finalsite__status_crosswalk`                                             | data team, with SRE confirming the mapping    |
| Finalsite exclude-ids Google Sheet                         | `stg_google_sheets__finalsite__exclude_ids`, applied inside `stg_finalsite__status_report`   | data team                                     |
| Locations Google Sheet                                     | `stg_google_sheets__people__locations`, `int_people__location_crosswalk`                     | data team                                     |

`stg_finalsite__status_report`'s cleaning (grade decode, `enrollment_type`
default, name casing, `active_school_year_display`) lives in the `finalsite`
source-system package; the kipptaf model of the same name is a thin
`union_relations` wrapper over the four district sources that adds `region`,
`_dbt_source_project` and the `exclude_ids` filter.
`int_focus__student_enrollment_roster` is likewise a thin kipptaf wrapper over a
`focus` package model.

## The dashboard views

### Progress to Goals: `rpt_tableau__fresh_dashboard_progress_to_goals`

What it shows: Enrolled and in-progress students counted against the five
Enrollment targets (`Seat Target`, `FDOS Target`, `Budget Target`,
`New Student Target`, `Re-Enroll Projection`), per school and per school and
grade.

Grain: One row per scaffold row (`academic_year`, `region`, `schoolid`,
`grade_level`, `enrollment_type` in `All`/`New`/`Returning`) per matched student
or goal record. `row_type` is `Student` (with `student_count = 1`) or `Goal`.

Reads:

- `int_tableau__fresh_enrollment_scaffold`: the rows. `School` rows are the
  `grade_level = -9` rows; `School/Grade Level` rows are every other row except
  region rollups (`schoolid != 0`). There are no region rows in this view.
- `int_people__location_crosswalk`: `school_level` for the `-9` rows, from
  `location_grade_band`. Grade rows take `school_level` from the scaffold.
- `int_tableau__finalsite_student_scaffold`: students whose `latest_status` is
  `Enrolled` or `Enrollment In Progress`.
- `int_google_sheets__finalsite__goals_pivot`: Enrollment targets at `School`
  and `School/Grade Level`, for the recruitment year.

Worth knowing:

- Each student is unioned in twice, once on their real `enrollment_type` and
  once on `aligned_enrollment_type = 'All'`, so the `All` rows add New and
  Returning together. Goals follow the same split: `New Student Target` lands on
  `New`, `Re-Enroll Projection` on `Returning`, everything else on `All`.
- A student with no assigned school (`schoolid = 0`) has no scaffold row to land
  on and does not appear.
- A student Finalsite has no record for never appears here. Those students are
  what `is_missing_finalsite_record` on the QC worklist catches.

### Aggregated: `rpt_tableau__fresh_dashboard_aggregated`

What it shows: Funnel counts (inquiries, applications, offers, pending offers by
age, waitlisted, deferred, enrollment in progress, conversion rates) against
funnel goals. Which goals and granularities reach it depends on the branch that
selects them (table below).

Grain: One row per goals-scaffold row per matched student. A goal with no
matching student keeps one row with NULL student columns.

Reads:

- `int_tableau__fresh_goals_scaffold`: the goal rows (every non-Enrollment goal
  whose key exists in the spine).
- `int_tableau__finalsite_student_scaffold`: the students, left-joined in five
  branches:

| branch                   | goals                                                | student join                                                                           |
| ------------------------ | ---------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Deferred / Waitlisted    | `Current`, `goal_name in ('Deferred', 'Waitlisted')` | school, grade, `goal_type`, and `goal_name = latest_status`                            |
| Enrollment In Progress   | `Current`, `School/Grade Level` only                 | school, grade, `goal_type`, and `goal_name = latest_status`                            |
| Pending Offers / Offers  | all granularities                                    | school, grade, `goal_type`, `goal_name`                                                |
| Inquiries / Applications | `Region/Grade Level` only                            | region and grade only (these students have no school yet)                              |
| Conversion               | `Ever`                                               | school, grade, `goal_type`, `goal_name`, plus the matching `Num` row for the numerator |

Worth knowing:

- `school_level` here comes from the goals sheet, not the scaffold, so it can
  differ from Progress to Goals for the same school and grade (see
  _`school_level` is banded per grade, and may disagree with the goals sheet_).
- `goal_name_value` is a Finalsite id column for counting. In the first four
  branches it is the matched student's `finalsite_id`. In the Conversion branch
  it is filled only when the same student also has the matching `Current`
  `... Num` row, restricted to `enrollment_type = 'New'`. A `... Num` status
  marks a student who reached the later stage of a conversion (for
  `Offers to Enrolled`, the enrolled ones), so counting `goal_name_value` gives
  the rate's numerator and counting `finalsite_id` its denominator.
- Region rollup goals carry `schoolid = 0`, and so does a Finalsite student with
  no assigned school. A branch that joins on `schoolid` therefore matches a
  `Region/Grade Level` goal only to unassigned students, never to the region's
  students as a whole. Only the Inquiries/Applications branch skips `schoolid`,
  so it is the only one where a region goal counts every student in the region
  and grade (see _Known issues, need to fix_).
- The `School`-granularity goals that reach this view are only `Offers` and
  `Pending Offers`, and they never match a student (see _Known issues, need to
  fix_).
- Only what the five branches select reaches this view: `Accepted` never does,
  and `Inquiries` and `App Target` only at `Region/Grade Level` (see _Known
  issues, need to fix_).

### The QC worklist: `rpt_tableau__fresh_dashboard_qc`

What it shows: A worklist, not a report: one row per student per problem, where
Finalsite and the SIS disagree. An empty result is the good outcome.

Grain: One row per student per fired flag (`flag_name`, with `flag_value` always
`true`).

Reads:

- `int_tableau__finalsite_student_scaffold` at
  `grouped_status_timeframe = 'Current'`: four flags, unpivoted into
  `(flag_name, flag_value)`, keeping only the rows where a flag fired.
- `int_extracts__student_enrollments`, `int_finalsite__contact_id_attributes`
  and `stg_finalsite__status_report`: the fifth flag,
  `is_missing_finalsite_record`, unioned on.

Worth knowing: see _The five flags, in plain language_ and _Implementation
notes_ below.

## The scaffold: `int_tableau__fresh_enrollment_scaffold`

One row per `(enrollment_academic_year, region, schoolid, grade_level)`, the
spine everything else joins against. The `rpt_tableau__fresh_dashboard_*` views
alias the year to `academic_year`. The scaffold is derived entirely from the SIS
and Finalsite; no hand-maintained sheet feeds it.

### How the spine is built

1. **`school_directory`**: one row per reporting school, from two SIS sources.
   NJ comes from `stg_powerschool__schools` at `state_excludefromreporting = 0`,
   which drops administrative rows such as the graduated-students school. Miami
   comes from `int_focus__schools` at `max_syear is null` (open schools only),
   inner-joined to `stg_google_sheets__people__locations` on `focus_school_id`
   to get the abbreviation and the PowerSchool-space `schoolid`. Focus's own
   school number is a Focus code, not a PowerSchool id, so this join is what
   puts Miami in the same id space. The join also requires `not is_pathways`:
   Pathways locations are not schools FRESH recruits into.
1. **`current_grade_levels`**: which grades each school serves, from current
   enrollment. NJ: `stg_powerschool__students` at `enroll_status = 0` (that
   table is current-state only). Miami: `int_focus__student_enrollment_roster`
   at `enroll_status = 0`, `academic_year = current_academic_year` and
   `rn_year = 1` (Focus carries several years, so the year filter scopes it).
   There is no explicit Miami exclusion on the PowerSchool branches; the kipptaf
   PowerSchool unions carry no Miami rows.
1. **`sis_scaffold`**: the directory joined to grade membership on
   `(schoolid, _dbt_source_project)`. Each PowerSchool instance assigns
   `schoolid` independently, so the source project is part of the key.

### The three row types the SIS can't produce directly

- **Whole-school totals (`grade_level = -9`)**: one row per school in the spine,
  with `school_level` NULL because a whole-school row spans bands.
  `scaffold_source` is `sis` if any of the school's grade rows came from the
  SIS, else `finalsite`.
- **Region rollups (`schoolid = 0`)**: a `select distinct` over
  `(region, grade_level, school_level)`, with `school` set to the region name.
  This is safe only because `school_level` is a function of grade alone.
- **Net-new schools/grades**: `finalsite_new`. School/grade pairs Finalsite has
  records for in the recruitment year, with an assigned school
  (`schoolid != 0`), that are not already in the SIS spine. The anti-join key is
  `(region, schoolid, grade_level)`.

  The CTE is gated by `finalsite_recruitment_year != current_academic_year`.
  While the two vars are equal the gate is closed and `finalsite_new` returns no
  rows. So a grade that is being recruited for, with nobody enrolled in the SIS
  yet, gets no scaffold row: its goals drop out of
  `int_tableau__fresh_goals_scaffold`'s inner join, and its Finalsite students
  have no row to land on in either reporting view. The gate opens only when the
  recruitment year runs ahead of `current_academic_year`. Both vars are in
  `src/dbt/kipptaf/dbt_project.yml`.

### `school_level` is banded per grade, and may disagree with the goals sheet

`school_level` is computed from grade (`>= 9` HS, `>= 5` MS, else ES), not read
from either SIS's per-school field. A per-grade value keeps the region rollup at
one row per grade, and some schools report different levels for different
grades.

These are NJ bands. Miami's real ES/MS boundary is 5/6, so Miami ES schools
serving grade 5 report their grade-5 rows as `MS` here, while the goals sheet
reports them as `ES`. This is accepted: the goals sheet stays hand-entered
because some goals are standard by grade across the network.

Consequence: Progress to Goals takes grade-row `school_level` from this
scaffold, and Aggregated takes it from the goals sheet (through
`int_tableau__fresh_goals_scaffold`), so Miami grade 5 can show different
`school_level` values on the two views.

### Miami is Focus-sourced

Miami's schools and grade membership come from `int_focus__schools` and
`int_focus__student_enrollment_roster`. The scaffold labels schoolid `30200805`
`Miami Tech`, the same label `int_finalsite__status_report_unpivot` resolves to
through `int_people__location_crosswalk`. No join in the chain keys on the
school name.

## The current academic year: a dedicated var, not `current_academic_year`

"The current Finalsite recruitment cycle" is the `finalsite_recruitment_year`
dbt var, read at every FRESH site that needs it. It is separate from
`current_academic_year` because Finalsite can carry two academic years of live
student data at once during a transition, and students and regions roll over on
their own timeline. There is no signal in the ingested data for "which year is
current now", and SRE's cycle has no fixed date. Always confirm the new year
with SRE before changing it; the fresh-dashboard skill has the file list.

The status crosswalk holds config for exactly one academic year at a time,
guarded by `test_stg_google_sheets__finalsite__status_crosswalk_single_year`
(`count(distinct file_year) = 1`).

## Goal definitions

The `Enrollment` goal_type group is plain numeric targets typed into the goals
sheet. It reaches the dashboard through
`int_google_sheets__finalsite__goals_pivot`, never through the status crosswalk:

| `goal_name`            | Definition                                                                  |
| ---------------------- | --------------------------------------------------------------------------- |
| `Seat Target`          | Total seats the school is targeting for the year.                           |
| `FDOS Target`          | Enrollment target as of the first day of school.                            |
| `New Student Target`   | Target count of new (not returning) students.                               |
| `Budget Target`        | The enrollment number the school's budget was built against.                |
| `Re-Enroll Projection` | Projected count of current students expected to persist (return) next year. |

Every other goal is a roll-up of the Finalsite funnel through the status
crosswalk. `Ever` goal types are `Inquiries`, `Applications`, `Offers`,
`Assigned School`, `Accepted` and the three `Conversion` rates; everything else
is `Current`.

| `goal_name` (`goal_type`)                                                          | Timeframe | Definition                                                              |
| ---------------------------------------------------------------------------------- | --------- | ----------------------------------------------------------------------- |
| `Inquiries`                                                                        | Ever      | Family ever submitted an inquiry.                                       |
| `App Target` (`Applications`)                                                      | Ever      | Family ever completed an application.                                   |
| `Offers Target` (`Offers`)                                                         | Ever      | Student was ever offered a seat.                                        |
| `Accepted`                                                                         | Ever      | Family ever accepted an offered seat.                                   |
| `Waitlisted`                                                                       | Current   | Current status is waitlisted.                                           |
| `Deferred`                                                                         | Current   | Current status is deferred.                                             |
| `Enrollment In Progress`                                                           | Current   | Student is mid-enrollment.                                              |
| `Pending Offers` (+ `<= 4 Days` / `>= 5 & <= 10 Days` / `> 10 Days`)               | Current   | Outstanding offer awaiting a family response, bucketed by days pending. |
| `Conversion`: `Accepted to Enrolled` / `Offers to Accepted` / `Offers to Enrolled` | Ever      | Conversion rate between two funnel stages.                              |

### Which goals exist at which granularity

Not every goal exists at every level. Expecting a value at a level a goal does
not live at produces a phantom gap, so check this before treating a missing row
as a problem. "scaffold" means the sheet carries rows for the combination with
no `goal_value`: they give the dashboard grid a row per school, grade and
status, and are never expected to receive a value. The table reflects the sheet
for AY2026; re-check it each cycle with the query below.

| `goal_name`                | `School` | `School/Grade Level` | `Region/Grade Level` |
| -------------------------- | :------: | :------------------: | :------------------: |
| `Budget Target`            |   yes    |          --          |          --          |
| `FDOS Target`              |   yes    |         yes          |          --          |
| `Seat Target`              |   yes    |         yes          |          --          |
| `Conversion` (3 names)     |    --    |         yes          |          --          |
| `Enrollment In Progress`   |    --    |    scaffold only     |          --          |
| `New Student Target`       |   yes    |         yes          |         yes          |
| `Re-Enroll Projection`     |   yes    |         yes          |         yes          |
| `App Target`               |   yes    |         yes          |         yes          |
| `Offers Target`            |   yes    |         yes          |         yes          |
| `Accepted`                 | scaffold |       scaffold       |       scaffold       |
| `Pending Offers` (4 names) | scaffold |       scaffold       |       scaffold       |
| `Inquiries`                |    --    |          --          |    scaffold only     |
| `Deferred`                 |    --    |          --          |    scaffold only     |
| `Waitlisted`               |    --    |          --          |    scaffold only     |

```sql
select
    goal_granularity,
    goal_type,
    goal_name,
    count(*) as sheet_rows,
    countif(goal_value is not null) as populated_rows,
from `teamster-332318`.kipptaf_google_sheets.stg_google_sheets__finalsite__goals
where enrollment_academic_year = <year>
group by goal_granularity, goal_type, goal_name
```

A NULL inside an otherwise populated combination is ambiguous: it may mean "no
goal here" or "nobody filled this in". Ask SRE rather than infer.

### `Conversion` goals are a flat per-grade lookup

SRE supplies the three `Conversion` rates by grade, identical across schools.
For AY2026 they collapse to two tiers: Kindergarten, and grades 1-12. A rate
change is a small uniform edit, and a reconciliation should check the shape (one
value per grade) rather than diff every row:

```sql
select grade_level, goal_name, count(distinct goal_value) as distinct_values,
from `teamster-332318`.kipptaf_google_sheets.stg_google_sheets__finalsite__goals
where enrollment_academic_year = <year> and goal_type = 'Conversion'
group by grade_level, goal_name
```

Anything other than `1` means a school has drifted off the common rate. The
`Conversion Rate` column on each region tab of SRE's workbook is a different
thing: an input used to derive "apps needed" from "new students needed".

### Sourced vs derived goals

Where SRE's workbook states a goal, the goals sheet matches it. Where the
workbook states nothing, the data team derives the value. At
`Region/Grade Level`, `App Target` is sourced from the cover sheet's region
grid, while `New Student Target` and `Re-Enroll Projection` are derived as the
rounded sum of the school rows.

So a region row need not equal the sum of its school rows. A gap of 1 is
rounding. `App Target` can differ by more, because the cover sheet can leave out
a grade that is new mid-expansion; do not "fix" it by summing. The
fresh-dashboard skill has the reconciliation procedure.

### A new school is not necessarily recruiting: Miami Tech

`Re-Enroll Projection` measures persistence in the network, not at one school,
so a school that did not exist last year can have returners. Miami Tech opened
to take KIPP's own grade-8 students into grade 9, with no external recruitment.
Its goals look broken and are correct:

| goal                   | expected      | why                                     |
| ---------------------- | ------------- | --------------------------------------- |
| `Re-Enroll Projection` | a real figure | the incoming cohort persists internally |
| `New Student Target`   | NULL          | not recruiting externally               |
| `App Target`           | NULL          | no application funnel                   |
| `Offers Target`        | NULL          | no lottery, so no offers                |

This is also why Miami Tech lacks the lottery categories (`Accepted`, `Offers`,
`Pending Offers`) at `School` granularity. Do not move the returners figure into
`New Student Target`.

### Full `grouped_status` → `goal_type` / `goal_name` crosswalk

`int_tableau__finalsite_student_scaffold`'s `roster` CTE renames
`grouped_status` into `goal_type` and `goal_name`. Only these change:

- `Ever`: `Applications` → `goal_name` `App Target`; `Offers` → `goal_name`
  `Offers Target`; `Accepted to Enrolled`, `Offers to Accepted` and
  `Offers to Enrolled` → `goal_type` `Conversion`.
- `Current`: the three `... Num` statuses → `goal_type` `Conversion`. A
  `... Num` status is the numerator of a conversion rate: the students who
  reached the rate's later stage. `goal_name` is never renamed for `Current`
  rows.
- `Current` `Pending Offers` also expands into the three day buckets.

Every other `grouped_status` passes through unchanged as both `goal_type` and
`goal_name`. To list the current `grouped_status` values:

```sql
select distinct grouped_status_timeframe, status_group_value,
from `teamster-332318`.kipptaf_google_sheets.int_google_sheets__finalsite__status_crosswalk_unpivot
```

`int_finalsite__status_report_unpivot` resolves `assigned_school` to a
PowerSchool `schoolid` and abbreviation through
`int_people__location_crosswalk`. Before Finalsite assigns a school (inquiries,
applications), the row falls back to `schoolid = 0` and
`school = 'No School Assigned'`, which is how those rows meet
`Region/Grade Level` goals. `int_tableau__finalsite_student_scaffold` also sets
`school` to the region for `Inquiries` and `Applications` rows.

## How Finalsite's `latest_status` becomes an expected enrollment status

`int_tableau__finalsite_student_scaffold` carries two enrollment-status columns:
`enroll_status` from the SIS, and `finalsite_expected_enroll_status`, derived
from `latest_status` alone. `rpt_tableau__fresh_dashboard_qc` exposes
`enroll_status` as `sis_enroll_status`.

The SIS side is `enrollment_lookup`, a `union all` of
`int_extracts__student_enrollments` (rows with an `infosnap_id`, which excludes
Miami's rows there) and `int_focus__student_enrollment_roster` bridged to
Finalsite through `int_finalsite__contact_id_attributes` on the Focus student
id. Both branches are scoped to the recruitment year, deduplicated per
`(academic_year, infosnap_id)` preferring an active record.

| `latest_status`                                                                                                                       | expected | meaning                     |
| ------------------------------------------------------------------------------------------------------------------------------------- | -------- | --------------------------- |
| `Enrolled`                                                                                                                            | `0`      | should be active in the SIS |
| `Mid Year Withdrawal`, `Never Attended`, `Summer Withdraw` ("left")                                                                   | `2`      | should not be active        |
| `Accepted`, `Assigned School`, `Did Not Enroll`, `Campus Transfer Requested`, `Parent Declined`, `Enrollment In Progress` ("pending") | `2`      | should not be active        |
| anything else                                                                                                                         | `NULL`   | no expectation              |

The values mirror the SIS's own `enroll_status` codes on purpose, because the
two columns are compared. The NULL case covers most of the funnel: a waitlisted
or deferred applicant has no business having an SIS record yet.

`is_enroll_status_mismatch` fires in two directions:

1. Finalsite says enrolled (`0`) but the SIS says withdrawn or graduated
   (`enroll_status in (2, 3)`).
2. Finalsite says the student should not be active (`2`) but the SIS says
   enrolled (`enroll_status = 0`). This covers both the "left" and the "pending"
   statuses; `latest_status` tells SRE which situation a row is.

SIS `1` and `-1` never trigger a mismatch. Beware the word "inactive": a
withdrawn student (`2`) often displays as inactive in the SIS and is caught,
while `enroll_status = 1` is also called inactive and is excluded on purpose.
Name the code, or say "withdrawn" and "graduated".

The pending list is SRE-owned. `Did Not Enroll` and `Parent Declined` read as
exits rather than pending states, and a bare `Accepted` may match no rows.
Confirm with SRE before changing the list.

### First day of school is hardcoded per region

`is_enrolled_fdos` is computed in `int_tableau__finalsite_student_scaffold` from
a first-day date hardcoded in that model:

| region           | first day |
| ---------------- | --------- |
| Newark, Paterson | August 28 |
| Camden           | August 24 |
| Miami            | August 14 |

The year comes from `var("finalsite_recruitment_year")`; month and day are
hardcoded and exposed as `custom_fdos_date`. The dates came from SRE and move
from year to year, so re-confirming them is a required rollover step.

The flag is `sis_entry_date <= custom_fdos_date`, where `sis_entry_date` is
`entrydate` (PowerSchool) or `startdate` (Focus). It checks entry only: a
student who enrolled before the first day and left before it still reads `true`.
It is a bare comparison, so a student with no SIS record reads NULL rather than
`false`. Do not wrap it in `if()` to match its siblings.

Expect no visible effect until school starts: at rollover both SISs give every
student the same bulk entry date, before any first day, so the flag reads `true`
for everyone with a record.

`int_extracts__student_enrollments` and `int_focus__student_enrollment_roster`
still compute their own `is_enrolled_fdos` for other consumers; this model reads
their entry dates instead. Their `is_enrolled_oct01` / `oct15` / `mar15` flags
pass through unchanged.

### The QC worklist flags

#### The five flags, in plain language

Each row is one student with one problem; a student with several problems
appears once per problem. Listed in SRE's triage order, most urgent first:

| #   | flag                          | what it means                                                                                                         | how it gets fixed                                                                                 |
| --- | ----------------------------- | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| 1   | `is_missing_sis_record`       | Finalsite says enrolled and the SIS has no enrollment record to compare against.                                      | Create or link the SIS record.                                                                    |
| 2   | `is_school_mismatch`          | Finalsite's assigned school is not the SIS school, so the student counts against the wrong school's targets.          | Confirm the true school, then fix whichever system is wrong.                                      |
| 3   | `is_enroll_status_mismatch`   | Finalsite and the SIS disagree about whether the student is enrolled (the two directions above).                      | Decide which system is right, then correct the other.                                             |
| 4   | `is_grade_level_mismatch`     | Finalsite's grade is not the SIS grade.                                                                               | Confirm the true grade, then fix whichever system is wrong.                                       |
| 5   | `is_missing_finalsite_record` | Enrolled in the SIS for the recruitment year, but Finalsite has no record at all. These make the dashboard count low. | Create or restore the Finalsite record. Until then the student is invisible on Progress to Goals. |

#### Implementation notes

- Three flags come from `int_tableau__finalsite_student_scaffold`.
  `is_missing_sis_record` is computed in the QC model as
  `finalsite_expected_enroll_status = 0 and enroll_status is null`, so it only
  fires for `Enrolled`: a student who should have an SIS record but was never
  advanced to `Enrolled` in Finalsite is invisible to it.
- `is_missing_finalsite_record` is unioned on rather than unpivoted because it
  describes a student Finalsite has never heard of, who cannot be in a
  Finalsite-sourced roster. It starts from `int_extracts__student_enrollments`
  (`enroll_status = 0`, recruitment year), takes the Finalsite id from
  `infosnap_id` or, for Miami, from `int_finalsite__contact_id_attributes`, and
  anti-joins against every `stg_finalsite__status_report` record, unscoped by
  year: a record under any cycle means Finalsite knows the student.
- The two absence flags are mirror images: for one Finalsite id, only one can
  fire. A child whose Finalsite record and SIS record are not linked by id (no
  or a wrong `infosnap_id`, or no Focus bridge row) fires both, on two rows: the
  Finalsite side looks for an SIS record and finds none, and the SIS side looks
  for a Finalsite record and finds none. See the "absent from the SIS" and
  "present but unlinked" question under _Open questions_.
- `is_grade_level_mismatch` and `is_school_mismatch` use
  `if(<cmp>, true, false)`, so they read `false`, not NULL, when the SIS side is
  missing. Do not use `is null` on them as a missing-SIS proxy. A student with
  no SIS record surfaces once, under `is_missing_sis_record`.
- During the window after the recruitment year moves ahead of the SIS (see
  _Known data model caveats_), the comparison flags fall silent network-wide and
  `is_missing_sis_record` carries the volume.

## Supporting models

In the family:

| model                                                    | role                                                                                                                                                                                                                                                                                |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `int_tableau__fresh_enrollment_scaffold`                 | The school x grade spine (above).                                                                                                                                                                                                                                                   |
| `int_tableau__fresh_goals_scaffold`                      | Non-Enrollment goals inner-joined to the spine on `(enrollment_academic_year, region, schoolid, grade_level)`; adds `grouped_status_timeframe`.                                                                                                                                     |
| `int_tableau__finalsite_student_scaffold`                | One row per student per `goal_type`/`goal_name`, with `latest_status`, days in status, SIS comparison columns and the QC flags. Materialized as a table.                                                                                                                            |
| `int_google_sheets__finalsite__goals_pivot`              | Every goals-sheet row pivoted to one column per Enrollment target, with `enrollment_type` derived from the goal name. No `goal_type` filter: Progress to Goals filters to `Enrollment`. The pivot takes `avg(goal_value)`, so a duplicate goal row is averaged, not doubled. Table. |
| `int_google_sheets__finalsite__status_crosswalk_unpivot` | The crosswalk unpivoted to one row per status per goal group; adds `grouped_status_order` (1-8 funnel sequence, 0 otherwise) and `grouped_status_timeframe`. Table.                                                                                                                 |
| `stg_google_sheets__finalsite__goals`                    | `select *` over the goals sheet. Table.                                                                                                                                                                                                                                             |
| `stg_google_sheets__finalsite__status_crosswalk`         | `select *` over the crosswalk sheet, plus `file_year` from the partition key. Table.                                                                                                                                                                                                |
| `int_finalsite__status_report_unpivot`                   | The 24 status-date columns of the status report as one row per enrollment, status and load partition, with `schoolid`, `school` and `status_order`. Also read by `rpt_gsheets__finalsite__log`, a retirement candidate pending a check with its user.                               |

Shared upstreams (outside the family):

- `stg_finalsite__status_report`: read by `int_finalsite__status_report_unpivot`
  for every status date, and by the QC model for Finalsite record existence,
  joined on `finalsite_enrollment_id`.
- `stg_google_sheets__finalsite__exclude_ids`: read by
  `stg_finalsite__status_report` to drop test records
  (`finalsite_enrollment_id not in` the sheet's `finalsite_student_id`).
- `int_finalsite__contact_id_attributes`: read by the student scaffold and the
  QC model for the Focus-to-Finalsite id bridge, joined on the Focus student id
  and `_dbt_source_project`.
- `int_extracts__student_enrollments`: read by the student scaffold and the QC
  model for NJ SIS enrollment, joined on `infosnap_id` and `academic_year`.
- `int_focus__schools`: read by the scaffold for Miami's school list, joined to
  the locations sheet on `focus_school_id`.
- `int_focus__student_enrollment_roster`: read by the scaffold for Miami grade
  membership (on `ps_schoolid`, `_dbt_source_project`) and by the student
  scaffold for Miami SIS enrollment (on the Focus student id).
- `stg_powerschool__schools` / `stg_powerschool__students`: read by the scaffold
  for the NJ school list and grade membership, joined on
  `(schoolid, _dbt_source_project)`.
- `stg_google_sheets__people__locations`: read by the scaffold for Miami school
  abbreviations and PowerSchool-space ids, joined on `focus_school_id`.
- `int_people__location_crosswalk`: read by
  `int_finalsite__status_report_unpivot` for `schoolid` (on
  `assigned_school = location_name`) and by Progress to Goals for `-9` row
  `school_level` (on `location_powerschool_school_id`).

## Inputs

All three sheets are Google Sheets external tables; ask the data team for the
links.

- **Finalsite goals sheet** (`src_google_sheets__finalsite__goals`): one row per
  year, region, school, grade, granularity, goal type and goal name, with the
  value. SRE supplies values in a new workbook each cycle; the data team pastes
  them in. The external table reads the sheet live, but
  `stg_google_sheets__finalsite__goals` and the pivot are tables frozen at their
  last build, so an edit is invisible until they rebuild. A dashboard number
  that doesn't match the sheet usually means the sheet changed after the last
  build: compare the sheet's Drive modified time against the table's
  `last_modified_time` in `kipptaf_google_sheets.__TABLES__`.
- **Finalsite status crosswalk sheet**: maps each Finalsite status and
  `enrollment_type` to funnel goal groups, for one year at a time. Column
  reference under _Rolling the dashboard over to a new cycle_.
- **Finalsite exclude-ids sheet**: Finalsite test and fake records to drop. A
  test record created today counts until its id is added.
- **SRE's goals workbook**: not read by dbt. It is the source the goals sheet is
  reconciled against (see _Sourced vs derived goals_).

## Decisions

- **Grade membership comes from current enrollment, not the declared grade
  span.** PowerSchool's `low_grade` is below what some schools serve, so
  `generate_array(low_grade, high_grade)` would add phantom grades, and nobody
  maintains it when a school's band shifts. Enrollment is self-maintaining. The
  cost: a newly opening grade with no enrolled student has no row until
  `finalsite_new` supplies it.
- **The net-new gate compares the two year vars.** Equal vars mean Finalsite and
  the SIS are on the same cycle, so a Finalsite school/grade missing from the
  SIS is treated as a data-entry error. Diverging vars mean Finalsite is
  recruiting ahead, which is when not-yet-enrolled grades should be trusted. The
  predicate is plain SQL, not a Jinja `if`, so the model compiles the same way
  every cycle.
- **First day of school is regional and hardcoded.** Focus computes its own flag
  against one network-wide first day, which marked most Miami students late;
  PowerSchool's is per school. The enrollment team reports against a regional
  date, so the date lives in this one model. One date per region is coarser than
  PowerSchool's per-school date for NJ; that imprecision is accepted.
- **`finalsite_expected_enroll_status` uses the SIS's own codes** so the two
  compared columns never give one number two meanings. `2` slightly overstates
  the pending statuses (truer: "no active record"), but the check only tests
  against SIS `0`, so no outcome changes.
- **Same-day status ties are not a QC flag.** The pending statuses in direction
  2 of `is_enroll_status_mismatch` cover the cases SRE needs to act on; the tie
  itself is handled with the Reset Protocol.

## Known data model caveats

These are properties of how Finalsite works, not defects. They explain recurring
gaps between raw Finalsite numbers and the dashboard.

- **Concurrent academic years, non-standardized rollover.** Two years of live
  student data can coexist; students and regions roll over on their own
  timeline.
- **Status dates are mutable and student-scoped, not year-scoped.** Editing a
  status in the Finalsite UI can overwrite its date. It is not an audit trail.
- **`grouped_status_order` (the 8-stage funnel sequence) is a best-assumption
  ordering.** Students can skip steps or move backward.
- **`detailed_status_ranking` (crosswalk sheet) is hand-duplicated into the
  `status_order` `CASE` in `int_finalsite__status_report_unpivot.sql`**, per the
  repo's rule against staging-layer joins to Google Sheets.
  `test_int_finalsite__status_order_matches_crosswalk_ranking` compares the
  sheet against a static list mirroring the `CASE`. Edit the `CASE`, the test's
  list and the sheet together.
- **Same-day status ties can pick the wrong latest status.** The pipeline
  compares dates, not timestamps, and breaks ties with `status_order desc`,
  which picks wrong for an exit status (`Parent Declined`, rank 15) against an
  in-progress one (`Enrollment In Progress`, rank 16) set the same day. The fix
  is the Reset Protocol. To find them, use the Progress to Goals tab's OPEN
  ROSTER button to see every student's current status, or the Finalsite Log
  sheet (`rpt_gsheets__finalsite__log`), which lists students with two or more
  statuses on their latest date. To prevent them, avoid two status changes for
  one student on the same day.
- **Ingestion lag.** `stg_finalsite__status_report` loads on a file-drop sensor,
  not a fixed schedule, so a cleanup done late in someone's day may not show
  until the next day's file. Whether this applies to Miami is unconfirmed.
- **SIS comparison columns go NULL for a while after the recruitment year moves
  forward.** Both branches of `enrollment_lookup` are scoped to the recruitment
  year, and neither SIS has rows for a year it has not rolled into. Until each
  SIS catches up, `enroll_status`, `sis_entry_date` and the `is_enrolled_*`
  flags are NULL for every student in that region. Expected; no action needed.
- **Fake or test Finalsite records inflate counts until someone adds their ids
  to the exclude-ids sheet.**

## Open questions

- **What is each dashboard tab for, who opens it, and which data source feeds
  it?** Landing Page, Progress to Goals, School Ops Team and SRE Team. This is
  an open request with the stakeholder. The answer decides which reporting
  models each audience depends on and whether the direct read of
  `int_tableau__finalsite_student_scaffold` can move to a `rpt_` model.
- **What is KIPP Purpose's new student target?** SRE's workbook states two
  different values for it on different tabs. Asked of the stakeholder; tracked
  on #5436.
- **A stray seat-target value on SRE's Miami tab** inflates SRE's own Legacy MS
  total. Only SRE can fix their workbook; tracked on #5436.
- **How should the QC checks handle retained students?** Retention can put
  Finalsite and the SIS legitimately out of step: Finalsite may carry the
  student at the next grade while the SIS has them repeating
  (`is_grade_level_mismatch`), and a repeated grade can keep a student at a
  school they would otherwise have left (`is_school_mismatch`, most likely at
  the grade 5/6 boundary). Options: suppress them, label them, or leave them
  firing. Choosing needs agreement on who records retention and when, and
  whether Finalsite's `Retained Date` is populated anywhere. Pending SRE.
- **QC questions from the AY2026 definitions review, pending SRE:** should the
  `Enrolled`-only gate on `is_missing_sis_record` widen? Should "absent from the
  SIS" and "present but unlinked" be separate flags (they need different fixes)?
  Is the triage order in _The five flags, in plain language_ still right?
- **Could `stg_finalsite__status_report.active_school_year` give a per-record
  rollover signal?** It is the school year a record is active under, and it is
  mixed at any moment. Comparing it to the recruitment year could replace the
  single network-wide anchor. An idea, not a design.
- **Historical or multi-year scaffold reporting is not supported.** Both SIS
  sources are scoped to the current cycle. Needs its own design if it becomes a
  requirement.

### Known issues, need to fix

- **School-granularity goals never match students in Aggregated.** Goals at
  `goal_granularity = 'School'` carry `grade_level = -9`, and every branch of
  `rpt_tableau__fresh_dashboard_aggregated` except Inquiries/Applications joins
  students on `grade_level` (lines 58, 108, 161, 261), which no student has as
  `-9`. The Inquiries/Applications branch is limited to `Region/Grade Level`. So
  `School` goal rows always show zero students:

  ```sql
  select
      goal_granularity,
      count(*) as goal_rows,
      countif(finalsite_id is not null) as rows_with_student,
  from `teamster-332318`.kipptaf_tableau.rpt_tableau__fresh_dashboard_aggregated
  group by goal_granularity
  ```

  `rows_with_student` is `0` for `School`.

- **Accepted goals, and App Target goals below region level, never reach
  Aggregated.** `int_tableau__fresh_goals_scaffold` carries them, but none of
  Aggregated's five branches selects `goal_type = 'Accepted'`, and the
  Inquiries/Applications branch keeps only
  `goal_granularity = 'Region/Grade Level'`, so `App Target` goals at `School`
  and `School/Grade Level` are dropped too. Compare the two models:

  ```sql
  select
      'goals_scaffold' as model, goal_type, goal_granularity, count(*) as goal_rows,
  from `teamster-332318`.kipptaf_tableau.int_tableau__fresh_goals_scaffold
  group by goal_type, goal_granularity
  union all
  select
      'aggregated' as model, goal_type, goal_granularity, count(*) as goal_rows,
  from `teamster-332318`.kipptaf_tableau.rpt_tableau__fresh_dashboard_aggregated
  group by goal_type, goal_granularity
  ```

  `Accepted` at every granularity, and `Applications` at `School` and
  `School/Grade Level`, appear for the goals scaffold only.

  Confirm with the stakeholder whether any tab expects them before adding a
  branch.

- **Region goals in the Offers, Pending Offers, Deferred and Waitlisted branches
  count only unassigned students.** These branches join students on `schoolid`
  (`rpt_tableau__fresh_dashboard_aggregated.sql` lines 57 and 160). A
  `Region/Grade Level` goal row has `schoolid = 0`, which matches only students
  with no school assigned, so the region-level count for these goals reads far
  too low. Most students at these stages have a school:

  ```sql
  select
      goal_type,
      countif(schoolid = 0) as unassigned_students,
      countif(schoolid != 0) as assigned_students,
  from `teamster-332318`.kipptaf_tableau.int_tableau__finalsite_student_scaffold
  where goal_type in ('Offers', 'Pending Offers', 'Deferred', 'Waitlisted')
  group by goal_type
  ```

  Only `unassigned_students` can reach a region row. The fix is to join region
  rows on region and grade only, as the Inquiries/Applications branch does.

- **The `fresh_dashboard` exposure reads
  `int_tableau__finalsite_student_scaffold` directly**, with no `rpt_` model
  buffering it (`src/dbt/kipptaf/models/exposures/tableau.yml`). The repo rule
  is that an external tool never reads an intermediate model directly.

- **`int_tableau__fresh_goals_scaffold`'s uniqueness test includes
  `goal_value`.** Two goals-sheet rows with the same key and different values
  pass the test and double the goal. The staging test on
  `stg_google_sheets__finalsite__goals` (key without `goal_value`) is what
  currently prevents it. Check the scaffold on its own key:

  ```sql
  select count(*) as duplicate_keys,
  from (
      select enrollment_academic_year,
      from `teamster-332318`.kipptaf_tableau.int_tableau__fresh_goals_scaffold
      group by enrollment_academic_year, region, schoolid, grade_level,
          goal_granularity, goal_type, goal_name, grouped_status_timeframe
      having count(*) > 1
  )
  ```

  The fix is to drop `goal_value` from the test's columns.

- **`int_finalsite__status_report_unpivot.latest_status_date` ignores the load
  partition.** The model's grain includes `_dagster_partition_key`, but the
  window partitions by `finalsite_enrollment_id, enrollment_academic_year` only,
  so a record loaded in several partitions gets one date across all of them.
  `_dagster_partition_key` names the Finalsite export file a row came from.
  There is one file per school year, and the key is that year in `2025_26` form,
  taken from the file name. Finalsite carries an enrollment into more than one
  school year's export, so the same record repeats across loads. Nothing reads
  the column today (`rpt_gsheets__finalsite__log` computes its own). Records
  loaded in several partitions:

  ```sql
  select count(*) as ids_in_several_partitions,
  from (
      select finalsite_enrollment_id, enrollment_academic_year,
      from `teamster-332318`.kipptaf_finalsite.int_finalsite__status_report_unpivot
      group by finalsite_enrollment_id, enrollment_academic_year
      having count(distinct _dagster_partition_key) > 1
  )
  ```

  Fix or drop the column.

- **`detailed_status_branched_ranking` is read by nothing.** It is declared in
  `stg_google_sheets__finalsite__status_crosswalk` and
  `int_google_sheets__finalsite__status_crosswalk_unpivot` and passed through,
  but no model reads it. Either wire up its intended use or remove it from both
  models and the sheet.

- **Pre-K: is it in scope?** The goals staging `accepted_values` test on
  `grade_level` rejects `-1`, so no Pre-K goal can be entered. The enrollment
  scaffold has no filter excluding `-1`, so a school with enrolled Pre-K
  students would get Pre-K spine rows with no possible goals. To check for Pre-K
  spine rows:

  ```sql
  select count(*) as prek_rows,
  from `teamster-332318`.kipptaf_tableau.int_tableau__fresh_enrollment_scaffold
  where grade_level = -1
  ```

  Decide with the stakeholder whether FRESH reports Pre-K, then either allow
  `-1` in the goals test or filter it out of the scaffold.

## Rolling the dashboard over to a new cycle

There is no fixed date. The rollover starts when SRE says its cycle has
advanced, not when `current_academic_year` bumps on July 1.

Order matters. `finalsite_recruitment_year` repoints the whole pipeline, and
several models inner-join sheets scoped to that year. Flipping the var before
the sheets carry the new year's rows does not error; it silently returns zero
rows.

### Steps, in order

| #   | Step                                                              | Owner           |
| --- | ----------------------------------------------------------------- | --------------- |
| 1   | Enter any new schools/grades in Finalsite under the new FS year   | SRE             |
| 2   | Agree which Finalsite enrollment year is now active               | SRE + data team |
| 3   | Update `status_crosswalk`'s partition key and confirm its columns | Analyst + SRE   |
| 4   | Supply the new goals workbook                                     | SRE             |
| 5   | Reconcile the goals sheet against SRE's workbook                  | Data team + SRE |
| 6   | Review `exclude_ids` for the new cycle's test records             | Analyst         |
| 7   | Re-confirm the four first-day-of-school dates                     | Data team + SRE |
| 8   | Bump `finalsite_recruitment_year` in `dbt_project.yml`            | Data team       |
| 9   | Build and verify the FRESH models                                 | Data team       |

#### 1-2. New schools and grades come from Finalsite

A school or grade being recruited for with nobody enrolled yet is entered in
Finalsite by SRE under the new Finalsite year. Once the recruitment year is
bumped ahead of `current_academic_year`, `finalsite_new` brings those rows in
(see _The three row types the SIS can't produce directly_). Agreeing on the
active year is the real gate on the rollover.

#### 3. `status_crosswalk`

- Replace the `_dagster_partition_key` value (column A) with the new year. The
  sheet holds one year at a time.
- Confirm with SRE that columns D, H, and I-P still make sense for the new
  cycle. They encode judgment about the funnel; there is no way to derive them.

This is the loudest failure mode: `latest_status_calc` inner-joins the crosswalk
on `_dagster_partition_key`, and the `Current` roster branch joins it on
`file_year`, so a key that doesn't match the Finalsite data drops every status
and the dashboard goes empty.

#### 4-5. Goals

SRE supplies a new workbook each cycle, so ask for it rather than assume last
cycle's. Then:

- Confirm goal names are unchanged: the join is on `goal_name`, so a renamed
  goal silently stops matching.
- Reconcile the workbook against `stg_google_sheets__finalsite__goals` at all
  three granularities; grade-level goals change independently of the cover
  sheet's school totals.
- Rebuild `stg_google_sheets__finalsite__goals` between rounds; it is a table.

Run this reconciliation whenever goals change, not only at rollover. SRE does
not always flag mid-year changes. The fresh-dashboard skill has the procedure.

#### 8. The var bump

One line in one file. Every model and test reads
`var("finalsite_recruitment_year")`.

After the bump, expect the SIS comparison columns to be NULL until each SIS
rolls over (see _Known data model caveats_).

### `status_crosswalk` column reference

The staging model is `select *`, so sheet columns map straight to model columns.
Bold rows are the ones SRE re-confirms each cycle.

| col     | column                                                                                                                                              | what it drives                                                                                                                                    |
| ------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| A       | `_dagster_partition_key`                                                                                                                            | The cycle year. Replaced at rollover; `file_year` is derived from it.                                                                             |
| B       | `enrollment_type`                                                                                                                                   | New vs Returning.                                                                                                                                 |
| C       | `detailed_status`                                                                                                                                   | The Finalsite status name being mapped.                                                                                                           |
| **D**   | `detailed_status_ranking`                                                                                                                           | Orders statuses. Hand-mirrored by the `status_order` `CASE`; change both.                                                                         |
| E       | `detailed_status_branched_ranking`                                                                                                                  | Read by nothing (see _Known issues, need to fix_).                                                                                                |
| F       | `valid_detailed_status`                                                                                                                             | `false` silently drops the row. "Is this status legitimate for this `enrollment_type`."                                                           |
| G       | `fs_status_field`                                                                                                                                   | The Finalsite date column the status came from.                                                                                                   |
| **H**   | `qa_flag`                                                                                                                                           | `true` silently drops the row.                                                                                                                    |
| **I-P** | `status_enrollment`, `status_group_numerator`, `status_group_denominator`, `conversion_metric_numerator_1..3`, `conversion_metric_denominator_1..2` | The goal-group mapping. Unpivoted into `status_group_name` / `status_group_value`, which is how a raw status becomes a `goal_type` / `goal_name`. |
| Q       | `file_year`                                                                                                                                         | Derived in the staging model from column A; not in the sheet.                                                                                     |
