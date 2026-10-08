# Academic Health Data Model

How the GPA and course-grade side of the Academic & Gradebook Health Suite
works: where its data comes from, how the dbt models turn PowerSchool grades and
the GPA goals sheet into the dashboard, and what to know before changing any of
it.

## What it is

The Academic & Gradebook Health Suite is a Tableau workbook that school and
network leaders use to watch high school and middle school grades during the
year: GPA distributions, course failures, students near the 3.0 line, and
progress against the network's GPA goals. Anthony Walters built it and owns it.

The workbook has two halves:

- **Academic health (this page).** Landing Page, Academic Health Home, Academic
  Health Schools, and Cumulative GPA Monitor. They read GPA and course grades.
- **Gradebook health.** Gradebook School Rollup and Gradebook Teacher View read
  `rpt_tableau__gradebook_audit`. The elementary comments view reads
  `rpt_tableau__gradebook_es_comments`. All three are covered on the
  [Gradebook Audit Data Model](gradebook-audit-data-model.md) page.

It is declared in dbt as the exposure `academic_gradebook_health_suite`, and
Dagster refreshes its extracts daily at 4 AM Eastern. The four `rpt_` models and
the goal models are views, so a refresh shows whatever the PowerSchool tables
beneath them held at their last build, not a live read of PowerSchool.

This page explains the models. How to read each view, tab by tab, is in the
end-user guides Walters drafted on open PR #5264; full view documentation is his
to add once that lands.

## How it fits together

```text
 PowerSchool: Newark, Camden, Paterson
 (stored grades, live gradebook, terms, grade scales, course enrollments)
   │
   ├─► base_powerschool__final_grades (current-year term and Y1 grades)
   │
   ├─► int_powerschool__gpa_term ─────► daily snapshot ─► ..._gpa_term_lookback
   ├─► int_powerschool__gpa_cumulative (current state, no year)
   │     └─► int_powerschool__gpa_cumulative_year (one row per year)
   └─► int_powerschool__student_course_grades_spine
                        │
          + int_extracts__student_enrollments (roster, demographics)
                        │
          ┌─────────────┴──────────────┐
          ▼                            ▼
 rpt_tableau__student_       rpt_tableau__gpa_cumulative_year
 course_grades                         │
          │                            │    GPA goals tab (Google Sheet)
          │                            │      └─► stg_ ─► int_google_sheets_
          │                            │          __gpa_goals
          │                            │              │
          │                            │     ┌────────┴──────────┐
          │                            │     ▼                   ▼
          │                            │  int_gpa__student_   int_gpa__goal_
          │                            │  goal_definitions    student_metrics
          │                            │     │                   ▼
          │                            ▼     ▼                int_gpa__goal_
          │               rpt_tableau__gpa_goal_progress      aggregations
          │                            │                         ▼
          │                            │              rpt_tableau__gpa_goals
          ▼                            ▼                         ▼
 Home and Schools tabs       Cumulative GPA Monitor     goal panels and tile
```

Three things carry the whole family:

- **The course-grain extract**, `rpt_tableau__student_course_grades`, holds one
  row per student, term, course, and gradebook category for this year and last
  year. The Home and Schools tabs read it.
- **The year-grain extract**, `rpt_tableau__gpa_cumulative_year`, holds each
  student's cumulative GPA at the end of every year. The Cumulative GPA Monitor
  reads it through `rpt_tableau__gpa_goal_progress`, which adds each student's
  goal.
- **The goal rollup**, `rpt_tableau__gpa_goals`, compares school, region, and
  network rates against the GPA goals sheet.

The workbook's embedded data sources are `rpt_tableau__gpa_goals`,
`rpt_tableau__gpa_goal_progress`, `rpt_tableau__gradebook_audit`,
`rpt_tableau__student_course_grades` (a custom-SQL source, shown in Tableau as
`rpt_tableau__student_course_grades+`), and one named `GPA Goals - Y1` whose
source is not yet confirmed. #5169 also records
`rpt_tableau__gpa_cumulative_year` embedded with nothing reading it (see _Known
issues, need to fix_).

## How the SQL treats Miami

Miami is not in the Health Suite. Miami's student information system moved to
Focus, and every GPA model here is built from PowerSchool, so the models exclude
Miami by name rather than show it empty:

- `rpt_tableau__student_course_grades` keeps Newark, Camden, and Paterson.
- `rpt_tableau__gpa_cumulative_year`, and so `rpt_tableau__gpa_goal_progress`,
  keep Newark and Camden only. Their year-grain source unions only the three NJ
  regions, and Paterson has no high school.
- `int_gpa__goal_student_metrics` keeps Newark, Camden, and Paterson, and so
  does every goal rate. Putting Miami back is tracked in #5171.

A Miami goal row on the goals sheet would match no students and never reach the
dashboard.

## Terms

### Kinds of GPA

"GPA" means several different numbers here, and they are not interchangeable.
Every one is credit-weighted: each course's grade points times its credit hours,
summed, divided by the credit hours. Courses PowerSchool marks
`excludefromgpa = 1` (lunch, homeroom, study hall) never count.

| Term                | Column                                  | What it is                                                                                             |
| ------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Term GPA            | `gpa_term`, `gpa_for_quarter`           | One marking period (Q1 to Q4); on the Y1 row, `gpa_for_quarter` holds the Y1 GPA                       |
| Semester GPA        | `gpa_semester`                          | S1 (Q1, Q2) or S2 (Q3, Q4), from the term rows                                                         |
| Y1 GPA              | `gpa_y1`                                | The year so far, from each course's running Y1 grade; for past years, the stored end-of-year Y1 grades |
| Cumulative GPA      | `cumulative_y1_gpa`                     | Every stored Y1 grade the student has at that school                                                   |
| Projected           | `cumulative_y1_gpa_projected`           | Cumulative plus this year's in-progress Y1 grades, as if the year ended today                          |
| S1 projected        | `cumulative_y1_gpa_projected_s1`        | Cumulative plus this year's semester 1 (as of Q2) grades                                               |
| Core cumulative     | `core_cumulative_y1_gpa`                | Cumulative over math, science, English, and social studies credit types, stored grades only            |
| Year-end cumulative | `cumulative_y1_gpa` on the year extract | Cumulative as of the end of each past year; on the current year, the projected value                   |

Cumulative GPA is kept **per student and school**. A student's high school
cumulative starts fresh in grade 9 and does not include middle school grades,
and a student who changes schools starts a new series.

`is_projected` marks the current-year row of the year extract, where the value
is the projection rather than a stored result. "As of today" columns
(`cumulative_y1_gpa_unweighted_as_of_today`) carry the running value, counting
only grades already stored; the projection is the basis for goals.

### Weighted and unweighted

**Weighted** grade points come from the course's own PowerSchool grade scale.
**Unweighted** grade points come from looking the course's percent up on that
scale's unweighted twin. The SQL names the twins: `KIPP NJ 2019 (5-12) Weighted`
and `KIPP NJ 2024 (5-12) Weighted - Honors` map to
`KIPP NJ 2019 (5-12) Unweighted`, and `NCA Honors` maps to
`KIPP NJ 2016 (5-12)`. Stored grades also map `NCA Honors` to `NCA 2011` before
2016, and a blank scale to a default. Other scales map to themselves, so for a
course on one the two numbers are equal.

Nothing in the SQL checks school level. Weighting exists only where a course is
on a weighted scale, and only high school courses are, so a middle school
student's weighted and unweighted GPAs are the same by design (#4978). Weighted
GPA can reach 5.33 and unweighted 4.33, so an unweighted GPA above 4.0 is not an
error.

Every goal and band on the dashboard uses **unweighted** GPA except the
`y1_gpa_weighted` goal metric.

### Bands and flags

| Term                                | Meaning                                                                                                                  |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `gpa_band_label`                    | Cumulative unweighted band: `3.5+`, `3.0-3.49`, `2.5-2.99`, `2.0-2.49`, `below 2.0`                                      |
| `gpa_band_projected_...`            | The same cut points as a number, 1 (below 2.0) to 5 (3.5 and up), the KIPP Foundation five-band scale                    |
| `is_on_cusp_3_0`                    | Cumulative unweighted GPA at least 2.75 and below 3.00                                                                   |
| `gpa_needed_for_cumulative_3_0`     | The unweighted Y1 GPA a student must average this year to finish at exactly 3.00; negative means already safe            |
| `is_gpa_band_slide`                 | Projected band at least one band below last year's band                                                                  |
| `F*`                                | Not a PowerSchool grade: a live gradebook grade below 50% is floored to 50% and labelled `F*`. Failure counts match `F%` |
| `need_60` to `need_90`, `need_next` | The percent needed in the current term for the year-to-date course grade to reach a target                               |
| Lookbacks                           | `gpa_y1_1_week_prior` and siblings: the Y1 GPA in effect at the end of the day 1, 2, or 4 weeks ago                      |

### Populations

| Term                 | Meaning                                                                                                          |
| -------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `rn_year = 1`        | A student's primary enrollment in a year; every model filters on it for one school per student-year              |
| `is_enrolled_recent` | The enrollment ran to the end of its school year or is active today, so mid-year leavers drop and graduates stay |
| `enroll_status`      | Current PowerSchool status, not as of the year: 0 active, 2 transferred out, 3 graduated                         |

### Goal terms

| Term               | Meaning                                                                                  |
| ------------------ | ---------------------------------------------------------------------------------------- |
| Rung (`org_level`) | Where a goal applies: `org` (the network), `region`, or `school`                         |
| `metric`           | `y1_gpa_weighted`, `y1_gpa_unweighted`, `cumulative_gpa_unweighted`, or `on_pace`        |
| `threshold`        | The GPA a student must reach, compared by `direction` (`>=` or `<=`)                     |
| `goal`             | The target share of students reaching the threshold, entered as a percent (69 means 69%) |
| Grade band         | `grade_low` to `grade_high`; one goal row covers each grade in the band                  |
| `aggregation_hash` | The key joining a rate to its goal: `org_9-12`, `Newark_11-11`, or `<schoolid>_10-10`    |
| `metric_rate`      | Students meeting the threshold over students with a value, rounded to three places       |

## Where the data comes from

| Source                                | What it provides                                                                          | Owner                                         |
| ------------------------------------- | ----------------------------------------------------------------------------------------- | --------------------------------------------- |
| PowerSchool, Newark, Camden, Paterson | Stored grades, live gradebook grades, terms, grade scales, courses, sections, enrollments | Schools enter grades; data team runs the load |
| GPA goals tab (Google Sheet)          | Goal threshold and target per year, rung, grade band, and metric                          | Data team enters; the network sets the goals  |
| Staff roster (ADP)                    | Teacher Tableau usernames and managers, for row-level security                            | People team                                   |
| Daily GPA snapshot                    | Yesterday's and earlier Y1 GPAs, for the lookbacks                                        | Built in the warehouse                        |

PowerSchool reaches every model through the kipptaf union views
(`int_powerschool__gpa_term`, `int_powerschool__gpa_cumulative`,
`int_powerschool__gpa_cumulative_year`,
`int_powerschool__student_course_grades_spine`), which read each region's
district project. Two of them, `int_powerschool__gpa_term` and
`int_powerschool__gpa_cumulative`, also union a Miami relation; the region
filters above keep it out.

The daily snapshot, `snapshot_powerschool__gpa_term`, records each student's Y1
GPA whenever it changes, captured once a day at 11 PM. The lookbacks read the
version in effect at the end of a past day. A lookback before the year's first
capture reads null.

Demographics, school, grade, advisory, ADA, and school leaders come from
`int_extracts__student_enrollments`, as of each year's primary enrollment.
Tutoring and tier flags come from `int_extracts__student_enrollments_subjects`.

## Dashboard models

Which tab reads which model, from the exposure and the workbook's data sources:

| Tab                                   | Model                                                                                 |
| ------------------------------------- | ------------------------------------------------------------------------------------- |
| Academic Health Home, Schools         | `rpt_tableau__student_course_grades`, plus `rpt_tableau__gpa_goals` for the goal tile |
| Cumulative GPA Monitor                | `rpt_tableau__gpa_goal_progress`                                                      |
| Landing Page                          | Navigation; its build is on open PR #5246                                             |
| Gradebook School Rollup, Teacher View | `rpt_tableau__gradebook_audit` (see the gradebook audit page)                         |

### `rpt_tableau__student_course_grades`: grades and GPA by course

**What it shows:** the Home and Schools tabs: GPA by term and year to date,
course grades and failures, students near a grade boundary, lowest gradebook
category per course, week-over-week GPA change, and the office hours roster.

**Grain:** one row per student, term (`Q1` to `Q4`, plus a `Y1` year row),
course, and gradebook category, for the current and prior academic year. Terms
that have not started yet are left out. Reads
`int_extracts__student_enrollments` (the student roster),
`int_powerschool__student_course_grades_spine` (course grades),
`int_powerschool__gpa_term` (term, Y1, and prior-quarter GPA),
`int_powerschool__gpa_cumulative` (cumulative and projected GPA),
`int_powerschool__gpa_cumulative_year` (last year's final cumulative),
`int_powerschool__gpa_term_lookback`,
`int_extracts__student_enrollments_subjects`, and `int_people__staff_roster`.

**Worth knowing:**

- Student-level columns repeat on every course and category row. Count students
  with a distinct count, never by summing rows.
- As-of-today measures (cumulative GPA, needed GPA, lookbacks, prior-quarter and
  prior-year comparisons) fill current-year rows only. Prior-year rows read null
  for them by design.
- `gpa_y1` on prior-year rows is the stored end-of-year value on every term,
  because PowerSchool stores only the final Y1 grade.
- `gpa_y1_prior_year` is last year's final weighted Y1 GPA, credit-weighted
  across schools for a student who attended two.
- `cumulative_y1_gpa_unweighted_change_from_prior_year` compares this year's
  projection with last year's final cumulative. Both are per school, so for a
  grade 9 student it compares a high school projection with a middle school
  result.
- `is_quarter_course_failing` matches `F%`, so it counts `F*`. It is null, not
  false, on an ungraded course: divide failures by graded rows, not all rows.
- `office_hours_priority_rank` ranks a student's courses in a term from lowest
  percent up; filter to rank 3 or less for a three-teacher list.
- `need_next` is the percent needed in the current term for the year-to-date
  grade to reach the next letter on the course's own scale, not the letter for
  the quarter alone.
- `section_or_period` is the section number below grade 9 and the period
  expression from grade 9.
- Its uniqueness test currently warns because of duplicate stored grades in
  prior years (see _Known issues, need to fix_).
- Do not relate it to the year extract on `student_number` alone; the match
  needs `academic_year` too, or a student fans out across every year.

### `rpt_tableau__gpa_goal_progress`: the Cumulative GPA Monitor

**What it shows:** the Cumulative GPA Monitor: cumulative unweighted GPA bands
by grade and school, students on the cusp of 3.0, whether 3.0 is still
reachable, and each grade and school against its goal.

**Grain:** one row per student and academic year, guarded by an error-level
uniqueness test. Reads `rpt_tableau__gpa_cumulative_year` and left joins
`int_gpa__student_goal_definitions` for the `cumulative_gpa_unweighted` goal.

**Worth knowing:**

- Every column of the year extract passes through, plus four goal columns:
  `gpa_goal_threshold` and the target share at the network, region, and school
  rung.
- The columns are listed by hand. A column added to the year extract does not
  appear here until it is added to this model's select list and contract too.
- Test `gpa_goal_proportion_org` to find rows with a goal. A null region or
  school target only means that rung has no goal; the network target still
  applies.
- The threshold is the network rung's. A region or school row on the sheet with
  a different threshold changes only that rung's target share here, while
  `rpt_tableau__gpa_goals` uses each rung's own threshold (see _Decisions_).
- The goal comparison on the dashboard is `>=`; the model does not carry the
  goal's `direction`.
- A singular test fails if any grade 9 to 12 row in a year the sheet covers has
  no network goal. A year counts as covered if it has a goal row for any metric,
  so a year with only Y1 goals still fails for missing cumulative goals.

### `rpt_tableau__gpa_cumulative_year`: cumulative GPA by year

**What it shows:** no tab reads it directly. It is the base of
`rpt_tableau__gpa_goal_progress` (see _Known issues, need to fix_ for its place
in the workbook).

**Grain:** one row per student and academic year, Newark and Camden only. Reads
`int_powerschool__gpa_cumulative_year` for the year-end values, inner joined to
the year's primary enrollment in `int_extracts__student_enrollments` on student,
year, school, and district, and left joins `int_powerschool__gpa_cumulative` for
the as-of-today values on the current year.

**Worth knowing:**

- Past years are recomputed from stored Y1 grades as running totals per student
  and school; the current year is the projection. Demographics are as of that
  year, but `enroll_status` is today's.
- The population is `is_enrolled_recent`, `enroll_status` 0, 2, or 3, and not
  out of district. A student-year whose grades were stored at a school other
  than that year's primary enrollment school drops at the join (#4343).
- `is_latest_graded_year` marks the most recent year with a non-null `gpa_y1` in
  Newark or Camden. The current year's `gpa_y1` comes from the live gradebook,
  so the flag moves to the current year as soon as any in-progress grade exists,
  not when Y1 grades are stored. Before then the monitor opens on the prior
  year.
- `gpa_band_label` is filled on every year; `gpa_band_as_of_today_label` only on
  the current year.
- `gpa_needed_for_cumulative_3_0` and `is_cumulative_3_0_attainable` are
  current-year only. They compute for any grade but mean something only in high
  school.

### `rpt_tableau__gpa_goals`: school, region, and network against goal

**What it shows:** the GPA goal panels: for each goal on the sheet, the share of
students meeting the threshold and whether that meets the goal.

**Grain:** one row per academic year, metric, and `aggregation_hash`, that is,
one per goal row on the sheet that matched at least one student. A thin select
over `int_gpa__goal_aggregations`.

**Worth knowing:**

- `metric_rate` divides students meeting the threshold by students with a value,
  not by every student in the grain. `n_students_in_grain`,
  `n_students_measured`, and `n_students_met` show all three counts. A rate is
  null, not zero, before a year's grades post.
- `progress_to_goal` is the rate over the goal, capped at 1.
- A grade with no goal row produces no row at all, indistinguishable from a
  grade with no students. Two singular tests on the sheet guard against a
  missing or unmatched goal (see _Process_).
- The population is high school students only, whatever grades the sheet names.
- `on_pace` goals always read null rates: the on-pace flags are placeholders
  that nothing populates yet.
- The cumulative metric reads the projected cumulative GPA, including for
  completed years (see _Known issues, need to fix_).

## Process: the GPA goals sheet

The goals behind every goal line live on one tab of a Google Sheet, staged as
`stg_google_sheets__gpa_goals`. The tab sits in the same workbook as the
gradebook audit tabs; ask the data team for access.

### What triggers it

The network sets GPA goals for a new school year, or changes one mid-year. Goals
exist per academic year, so a year with no rows has no goal lines.

### Inputs

One row per goal, with these columns in this order:

| Column                    | Holds                                                                 |
| ------------------------- | --------------------------------------------------------------------- |
| `academic_year`           | Start year: 2026 means SY26-27                                        |
| `org_level`               | `org`, `region`, or `school`                                          |
| `region`                  | `Newark`, `Camden`, or `Paterson`; required on region and school rows |
| `schoolid`                | PowerSchool school number; school rows only                           |
| `grade_low`, `grade_high` | The grade band; equal for a single grade                              |
| `metric`                  | One of the four metrics under _Goal terms_                            |
| `threshold`               | The GPA to reach, for example 3.0                                     |
| `direction`               | `>=` or `<=`                                                          |
| `goal`                    | Target percent of students, 0 to 100                                  |

### Steps

1. Edit the tab. The sheet is read through a named range and by column position,
   so a column inserted mid-tab shifts every value after it, and a row past the
   range's end is ignored.
2. A Dagster sensor polls the sheet every few minutes and rebuilds the staging
   table after an edit. Its tests are error-level: one row per year, rung,
   region, school, grade band, and metric; `grade_low` no higher than
   `grade_high`; known values for `org_level`, `metric`, and `direction`; and
   `goal` between 0 and 100.
3. `int_google_sheets__gpa_goals` turns the percent into a proportion, labels
   the grade band, and builds `aggregation_hash`. Four singular tests then check
   the sheet against the students:
   - every region and school goal sits inside a network goal's grade band for
     the same year and metric, or its students would lose the goal silently;
   - every goal matches at least one student in years the student data covers,
     which catches a mistyped school number or region;
   - within a rung, every grain covers the same grades, which catches one school
     missing a grade its peers have;
   - every high school student in a goal year gets a network goal on the
     Cumulative GPA Monitor.
4. The goal views read the staging table directly, so the next Tableau refresh
   at 4 AM shows the change.

### Outputs

- `rpt_tableau__gpa_goals`: rates against each goal row, for the goal panels.
- `rpt_tableau__gpa_goal_progress`: each student's cumulative goal at the three
  rungs, for the Cumulative GPA Monitor's goal lines.

### Who runs it and when

The data team enters goals when the network sets them, usually before the school
year starts, and checks the tests after the rebuild. Anthony Walters owns the
goal models. School rows are optional: a school with no goal still shows the
network target.

## Supporting models

### The goal chain

- `int_google_sheets__gpa_goals`: the sheet with `goal_proportion`,
  `grade_band`, `aggregation_hash`, and `higher_is_better` added. One row per
  year, metric, and hash.
- `int_gpa__goal_student_metrics`: one row per high school student, school, and
  year, carrying Y1 GPA weighted and unweighted (from the current-term row of
  `int_powerschool__gpa_term`) and cumulative unweighted GPA (the projection,
  from `int_extracts__student_enrollments`). A student with no GPA yet stays in
  with null measures, which counts in `n_students_in_grain` but not in the rate.
- `int_gpa__goal_aggregations`: joins those students to each goal by year and
  grade band, three times (school on school and region, region on region,
  network on nothing more), and computes the counts, rate, `is_goal_met`, and
  `progress_to_goal`.
- `int_gpa__student_goal_definitions`: one row per student, year, and metric
  with a network goal, carrying the network threshold and the target share at
  each rung. Its only filter is `rn_year = 1`; its only reader,
  `rpt_tableau__gpa_goal_progress`, supplies the population.

### The PowerSchool GPA models

These build in each NJ district project from the shared `powerschool` package
and are unioned in kipptaf.

- `int_powerschool__gpa_term`: one row per student, school, year, and term with
  term, semester, and Y1 GPA and the failing-course count. The current year
  comes from the live gradebook, past years from stored grades. `is_current`
  marks the term whose dates cover today, or Q4 for a past year.
- `int_powerschool__gpa_cumulative`: one row per student and school, current
  state only (no year). Stored Y1 grades give the cumulative; adding this year's
  unstored Y1 grades for courses whose term covers today gives the projection.
  It also computes the GPA needed for a 3.0 and whether it is attainable.
  Through `int_students__gpa_cumulative`, it also reaches every reader of
  `int_extracts__student_enrollments`.
- `int_powerschool__gpa_cumulative_year`: one row per student, school, and year.
  Completed years are running totals of stored Y1 grades per student and school;
  the current year is the projection from `int_powerschool__gpa_cumulative`,
  copied as is.
- `int_powerschool__gpa_term_lookback`: current year only, one row per student
  and school, with the Y1 GPA and failing count in effect at the end of the day
  1, 2, and 4 weeks ago, from the daily snapshot. The snapshot never closes a
  row for a student who leaves, so readers must scope by enrollment, which the
  extract does.
- `int_powerschool__student_course_grades_spine`: one row per student, course,
  term, and category. Current-year grades come from the live gradebook, with an
  in-progress `Y1` row from the current term; past years from stored grades. It
  builds the `need_*` columns, the lowest-category drivers, and
  `office_hours_priority_rank`, and drops lunch, advisory, study hall, and early
  dismissal courses by course number.

### Shared upstreams

- `base_powerschool__final_grades`: read by the GPA term, cumulative, and course
  spine models for current-year term and running Y1 grades. The term model reads
  it directly; the cumulative model joins enrollments to it on student and year.
  Quarters weigh 25 each in a course with no exam; with exams, 22 per quarter
  and 5 per exam term.
- `stg_powerschool__storedgrades`: read for every stored grade, joined on
  student, course, year, and store code; it also names each grade's unweighted
  scale.
- `int_powerschool__gpa_term`: also read by the goal metrics for Y1 GPA, joined
  on student, school, year, and district; the daily snapshot captures its
  current-term rows.
- `int_powerschool__gpa_cumulative`: also read by the course extract and the
  year extract for as-of-today values, joined on student, school, and district.
- `int_students__gpa_cumulative`: read by `int_extracts__student_enrollments`
  for cumulative and projected GPA, joined on student number and school only,
  with no year. It adds Focus GPAs for Miami, which this family filters out.
- `int_extracts__student_enrollments`: read by every model for the roster and
  demographics, joined on student, year, school, and district, filtered to
  `rn_year = 1`.

## Inputs

The only hand-maintained input is the GPA goals tab described under _Process_.
Everything else is PowerSchool as teachers and schools enter it: grade scales
and course credit hours set up in PowerSchool decide grade points, weighting,
and GPA eligibility.

## Decisions

### Cumulative GPA is kept per school

Cumulative GPA accumulates per student and school, matching how PowerSchool
computes it. High school GPA therefore starts in grade 9 without middle school
grades, which is what the high school goals measure. The cost is that a student
who transfers mid-career starts a new series, and a grade 9 year-over-year
comparison sets a high school number against a middle school one.

### An unmeasured student is not a non-achiever

Goal rates divide by students who have a GPA, not by every enrolled student. A
student without grades yet is unknown, and counting them as missing the goal
would make every rate read low in the first weeks of the year and zero before
grades post. The in-grain count is kept beside the rate so the gap stays
visible.

### Populations follow enrollment dates, not status

`enroll_status` is current and student-level, so filtering on it drops every
graduate from every completed year and reported past senior classes at almost
zero. The goal and year models use `is_enrolled_recent` instead, which keeps a
year the student finished and drops a year they left partway through.

### The network rung defines who has a goal

A student has a goal when a network goal covers their grade; region and school
targets attach to that row when they exist. So a school without its own goal
still shows the network line, and the threshold on the Cumulative GPA Monitor is
always the network's. School-level goals are not being set this year (#5169).

### The goal wrapper is a separate model

`rpt_tableau__gpa_goal_progress` adds goal columns to the year extract instead
of changing the extract itself. Two published dashboards read the extract
through a Tableau relationship that declares it unique, and the extract is a
view, so a join that fanned it out would ship without an error. Folding the
wrapper into the extract is planned; until then its columns are maintained by
hand.

### Prior-year Y1 GPA is the final value

PowerSchool stores only the end-of-year Y1 grade, so there is no "last year as
of this quarter" to compare against. Comparisons with last year use its final Y1
and final cumulative GPA.

### The Cumulative GPA Monitor opens on the latest graded year

The current year has schedules but no grades for its first weeks, so the
monitor's default year is the most recent year with posted Y1 grades
(`is_latest_graded_year`) rather than the current one.

## Known issues, need to fix

### Completed-year cumulative goal rates use today's projection

Tracked in #5562.

`int_gpa__goal_student_metrics` takes `cumulative_gpa_unweighted` from
`int_extracts__student_enrollments`, which joins cumulative GPA on student and
school with no year. Every past year of a student at their current school
therefore carries today's projection, not that year's final value, so the
`cumulative_gpa_unweighted` rows of `rpt_tableau__gpa_goals` for completed years
do not report what those years ended at. Most past-year students differ:

```sql
select
    m.academic_year,
    count(*) as n_students,
    countif(
        abs(m.cumulative_gpa_unweighted - cy.cumulative_y1_gpa_unweighted)
        > 0.005
    ) as n_differ_from_year_end,
from `teamster-332318.kipptaf_gpa.int_gpa__goal_student_metrics` as m
left join
    `teamster-332318.kipptaf_tableau.rpt_tableau__gpa_cumulative_year` as cy
    on m.student_number = cy.student_number
    and m.academic_year = cy.academic_year
group by m.academic_year
```

The fix is to read the year-end value from
`int_powerschool__gpa_cumulative_year` for completed years. The Cumulative GPA
Monitor is not affected: it reads the year extract.

### Honors courses read weighted points as unweighted this year

Tracked in #5563.

Stored grades map the `KIPP NJ 2024 (5-12) Weighted - Honors` scale to its
unweighted twin by name, but the current-year path maps unweighted scales by id
in `base_powerschool__sections`, and only covers the 2016 and 2019 weighted
scales. Honors courses on the 2024 scale therefore carry weighted points in
every current-year unweighted GPA: in-progress Y1, projected cumulative, and the
needed-GPA columns. Scale 1075 tops out at 4.83, so this year's unweighted
honors GPA can pass 4.33. Stored past years are correct.

```sql
select
    _dbt_source_project,
    academic_year,
    count(distinct course_number) as n_courses,
    countif(y1_grade_points != y1_grade_points_unweighted) as n_rows_differing,
from `teamster-332318.kipptaf_powerschool.base_powerschool__final_grades`
where courses_gradescaleid_unweighted = 1075
group by _dbt_source_project, academic_year
```

`n_rows_differing` reads 0 for every honors course. The mapping change belongs
with the grade-scale work in #5092, which rewrites the same `case`.

### Some student-years drop from the year extract

The year extract's inner join to the year's primary enrollment includes the
school, so a year whose grades were stored at another school, and a year with no
primary enrollment row, drop out. The student's GPA history shows a gap for
those years. Tracked in #4343.

### Duplicate stored grades

PowerSchool holds more than one stored grade for some student, course, year, and
store code, each a real record (#5221). In the course extract they surface as
duplicate prior-year rows, so its uniqueness test is at warn until the cleanup
lands (`TODO(#3915)` in the model's YAML). Count them with:

```sql
select
    count(*) - count(
        distinct format(
            '%T|%T|%T|%T|%T|%T',
            _dbt_source_relation,
            studentid,
            academic_year,
            `quarter`,
            course_number,
            category_name_code
        )
    ) as n_duplicate_rows,
from `teamster-332318.kipptaf_tableau.rpt_tableau__student_course_grades`
```

### Failing count reads 0 with no graded work

`n_failing_y1` sums a flag, so a student with a GPA row but no graded Y1 course
reads 0 failures instead of unknown. It reaches `gpa_n_failing_y1` and
`n_failing_y1_prior_quarter` on the course extract. The lookbacks already guard
it. Tracked, with its query, in #5173.

### Y1 `F*` label is on the wrong scale

Tracked in #5564.

`base_powerschool__final_grades` labels a Y1 grade `F*` when
`y1_percent_grade < 0.500`, but that column is on a 0 to 100 scale, so only a Y1
of 0% gets the label. Other failing Y1 grades read `F`. Failure counts match
`F%`, so they are unaffected; only the label differs from the term grades, where
`F*` means below 50%.

### Workbook data sources to confirm with Walters

- The exposure lists `rpt_tableau__gpa_cumulative_year`, but no tab reads it
  directly. #5169 records it embedded as its own data source and related into
  `rpt_tableau__student_course_grades+`, with no worksheet reading a column from
  either, and proposes removing both. Once decided, drop it from the exposure or
  keep it.
- The data source `GPA Goals - Y1` has no known model behind it. Confirm what it
  reads and add that model to the exposure.
- Two more exposures read this family: `gpa_goals_dashboard`
  (`rpt_tableau__gpa_goals`) and `cumulative_gpa_monitor`
  (`rpt_tableau__gpa_goal_progress`). Both carry placeholder URLs
  (`TODO(#4581)`, `TODO(#4619)`). Confirm whether they are separate published
  workbooks or the Health Suite tabs, and retire or fill them.

### Smaller items

- `on_pace` has no data: `is_on_pace` and its denominator are nulls pending
  follow-on work (`TODO(#4581)`), so an `on_pace` goal row reads a null rate.
- Miami is out of the goal population until its GPA data is available (#5171).
- `base_powerschool__sections` tests `case cou.gradescaleid when null`, which
  never matches, so the blank-scale default that stored grades apply never
  applies to current-year courses.
- Past-year `gpa_term` multiplies by stored `potentialcrhrs` in the numerator
  but divides by course `credit_hours` (`int_powerschool__gpa_term.sql`). Impact
  not measured; a likely bug where the two differ.
- The singular test `int_google_sheets__gpa_goals__every_goal_aggregates` and
  its YAML description say Paterson is excluded from the student metrics. It is
  not any more; the reasoning (Paterson has no high school, so a Paterson goal
  matches nobody) still holds. Correct the wording.

### Open work that touches this family

- #5183 names the school on `rpt_tableau__gpa_goals` and labels every rung.
- #5140 adds the projected four-year college enrollment goal beside the
  cumulative GPA goal.
- #5092 supports pass/fail courses without dropping them from grade reporting.
- #4655 adds a missing-assignment count to the course extract.
- #4978 proposes a glossary of GPA terms and the high-school-only weighting
  rule.
- #5169, #5174, #5190 (with PR #5198), and PR #5246 are dashboard changes: open
  decisions on the Academic Health tabs, gaps against the HS GPA monitoring
  protocol, cards and captions on the Cumulative GPA Monitor, and the landing
  page.

## The Gradebook and GPA Dashboard

The older Tableau workbook, exposure `gradebook_and_gpa_dashboard`, reads
`rpt_tableau__gradebook_gpa` and `rpt_tableau__gradebook_gpa_cumulative`. The
Health Suite replaced it. Dagster no longer refreshes its extracts: the exposure
carries no refresh schedule. Anthony Walters decides when to retire it; retiring
a model here means disabling it, never deleting it.

## Yearly upkeep

| Who         | Does what                                                                                        |
| ----------- | ------------------------------------------------------------------------------------------------ |
| The network | Sets GPA goals and grading policy for the year                                                   |
| T&L         | Usually sends a grading-policy Google Doc for the next year                                      |
| Data team   | Enters goals on the sheet, reads the policy for code changes, checks the tests and dashboard     |
| Automatic   | `current_academic_year` rolls over in July; sheet edits rebuild staging; Tableau refreshes daily |

Each school year:

1. **Grading policy.** T&L usually send a grading-policy document for the next
   year, and it decides whether code changes: term weights, grade scales,
   failing rules, excluded courses. None exists for this year yet; Walters adds
   it here when it arrives.
2. **Goals.** Enter the new year's rows on the goals tab, network rung first,
   and confirm the four singular tests pass.
3. **Rollover.** In July `current_academic_year` moves forward, and the course
   extract's two-year window, the projection, and the lookbacks move with it.
   The dashboard keeps opening on the last graded year until new grades post.
4. **Grade scales.** A new weighted scale in PowerSchool needs its unweighted
   twin mapped in both `stg_powerschool__storedgrades` (by name) and
   `base_powerschool__sections` (by id), or its unweighted GPA equals the
   weighted one.
5. **Regions.** A Paterson high school appears in the course extract and goal
   metrics on its own, but the year extract lists Newark and Camden by name.
   Miami returns when #5171 lands.

## Owner

The Data Team. Anthony Walters owns the Academic & Gradebook Health Suite and
this model family; questions about the dashboard or the goals go to him.
