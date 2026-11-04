# GPA quarter target, quickest win, and pace status

Design for [#5768](https://github.com/TEAMSchools/teamster/issues/5768). Depends
on [#5756](https://github.com/TEAMSchools/teamster/issues/5756) (PR #5761) for
the needed-GPA denominator.

## Problem

School staff want, per high school student, what to earn in each course this
quarter to finish the year at or above a 3.0 unweighted cumulative GPA, in a
form they can use in a monthly advisor meeting. Today the Cumulative GPA Monitor
shows the unweighted Y1 GPA needed for the year, and the Gradebook rollup shows
the percent needed this quarter for each course to reach a fixed cutoff. Nothing
ties the two together per student, and nothing updates as quarters close.

A quarter GPA target is the wrong unit. Quarter GPA is not stored after the
quarter ends, and quarter GPAs do not average to the Y1 GPA. A course's Y1 is
the weighted average of its quarter percents, and every grade scale in use
shares the same percent cutoffs, so a percent per course is the unit that adds
up.

## Goals

- One target letter per student, derived from the student's own needed
  unweighted Y1 GPA, floored at B.
- One pace percent per course for the remaining quarters, recomputed daily.
- One highest-leverage course per student per quarter.
- A pace status with three states plus unknown.
- The weighted Y1 GPA needed, for reconciling against the GPA PowerSchool shows.
- Surfaced on the GPA roster sheet and the Cumulative GPA Monitor.

## Non-goals

- A quarter GPA target, in any form.
- A per-course optimizer that picks the cheapest grade mix. The uniform letter
  is one sufficient plan; the quickest win is where unequal effort surfaces.
- Dashboard labels and tooltips. Display wording is a Tableau decision. The
  model carries neutral values.
- Tableau changes to the Gradebook rollup, the office-hours list, and the
  Monitor's "credits in progress" label. Same release, separate work.

## Facts the design rests on

Verified against prod on 2026-10-06.

- Grade scales 976 (unweighted), 991 (weighted), and 1075 (honors) share every
  percent cutoff. 991 adds 1.0 grade point at every passing letter; 1075 adds
  0.5. F is 0 on all three.
- A course's Y1 percent is the weighted average of its term percents: 25 per
  quarter, or 22 per quarter plus 5 per exam term where exams exist.
  `base_powerschool__final_grades` carries the weights as
  `term_weighted_points_possible` and the running totals.
- Credit hours and unweighted Y1 points are identical across every term row of a
  course in all three districts, so a course-grain `max()` is exact.
- Weighted minus unweighted Y1 equals the credit-weighted bump from the schedule
  for 1,831 of 1,863 AY2025 high schoolers within 0.011. The 22 below failed a
  weighted course; the 10 above are off by at most 0.04.
- Q1 ends 2026-11-02 in Newark and Camden. Q2 runs to 2027-02-01. Last year,
  first-semester Y1 grades were stored in February.

## Data model

Three new kipptaf models, all reading existing columns, plus columns on two
existing extracts. Student-level outputs are tier-3 PII; every new model is
tagged `contains_pii`.

### `int_powerschool__student_y1_target`

One row per student and school for the current year.

| Column                                                                | Definition                                                                                                                                                                                                   |
| --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `gpa_needed_unweighted`                                               | `gpa_needed_for_cumulative_3_0` from `int_powerschool__gpa_cumulative`, rounded to 4 decimals before any lookup                                                                                              |
| `target_cutoff_percent`, `target_letter_grade`, `target_grade_points` | The lowest row of the unweighted scale whose `grade_points` is at or above `gpa_needed_unweighted`, from `int_powerschool__gradescaleitem_lookup`, floored at the B row                                      |
| `schedule_bump`                                                       | Σ(bump × `potential_credit_hours`) over the current-year GPA courses, divided by Σ credits; bump is 1.0 for scale 991, 0.5 for 1075, else 0, from `courses_gradescaleid` on `base_powerschool__final_grades` |
| `gpa_needed_weighted`                                                 | `gpa_needed_unweighted + schedule_bump`                                                                                                                                                                      |
| `pace_status`                                                         | See below                                                                                                                                                                                                    |
| `n_courses_below_target`                                              | Count of unlocked courses whose current Y1 percent is below `target_cutoff_percent`                                                                                                                          |

Status values, in precedence order:

| Value                 | Rule                                                                                          |
| --------------------- | --------------------------------------------------------------------------------------------- |
| `unknown`             | `is_cumulative_3_0_attainable` is null, or `gpa_needed_unweighted` is null                    |
| `goal_not_attainable` | `is_cumulative_3_0_attainable` is false, or `gpa_needed_unweighted` exceeds the scale max     |
| `on_pace`             | `cumulative_y1_gpa_projected_unweighted` is at or above 3.0, or `n_courses_below_target` is 0 |
| `not_on_pace`         | Otherwise                                                                                     |

`gpa_needed_unweighted` at or below 0 reads `on_pace` with the target floored at
B. The floor is a display rule, not a math rule: a student above 3.0 still sees
a B target.

### `int_powerschool__course_pace`

One row per student, course, and current year, for unlocked GPA courses.

| Column               | Definition                                                                                                     |
| -------------------- | -------------------------------------------------------------------------------------------------------------- |
| `y1_percent_current` | `y1_percent_grade_adjusted` on the current termbin row                                                         |
| `points_banked`      | `term_weighted_points_earned_adjusted_running` on the last completed term row, 0 before Q1 ends                |
| `total_weight`       | `y1_weighted_points_possible`                                                                                  |
| `remaining_weight`   | `total_weight` minus the weight of completed terms, including the in-progress term                             |
| `pace_percent`       | `(target_cutoff_percent × total_weight − points_banked) / remaining_weight`, null when `remaining_weight` is 0 |
| `is_below_target`    | `y1_percent_current < target_cutoff_percent`                                                                   |
| `is_secured`         | `pace_percent <= 50`, the live-gradebook floor                                                                 |
| `is_locked`          | Every termbin for the course has ended; the row is excluded from pace and kept in the GPA                      |

The in-progress term belongs to `remaining_weight`, not `points_banked`, so the
pace does not swing with each posted assignment. Exam terms count in
`remaining_weight` and the pace applies to them. The spec does not solve for a
quarter pace under an assumed exam score; a later revision may.

`pace_percent` is the same algebra as the existing `need_*` columns, which are
affine in the target, extended from the current term to all remaining terms. The
model recomputes from the running totals rather than deriving from `need_60` and
`need_70`, so the exam weights and the remaining-terms span are explicit.

### `int_gpa__course_quickest_win`

One row per student and course, ranked within student.

| Column                                                          | Definition                                                                                                                                                                     |
| --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `next_letter_grade`, `next_cutoff_percent`, `next_grade_points` | The lowest unweighted row with strictly more grade points than the course's current unweighted Y1 points                                                                       |
| `points_gained`                                                 | `next_grade_points − y1_course_in_progress_grade_points_unweighted`                                                                                                            |
| `need_gap`                                                      | `pace_percent_to_next − y1_percent_current`, where `pace_percent_to_next` is the pace formula with `next_cutoff_percent` as the target, on the raw percent before the 50 floor |
| `score`                                                         | `potential_credit_hours × points_gained / greatest(need_gap, 1.0)`                                                                                                             |
| `quickest_win_rank`                                             | Rank by `is_below_target` desc, `score` desc; null when `pace_percent_to_next > 100`, `need_gap <= 0`, or the course is locked                                                 |

The existing `need_next` divides by the current term weight against a
year-to-date total and over-ranks second-semester courses about 1.5x, which is
why the model derives from the full-year weights.

### Extract changes

`rpt_gsheets__gpa_roster` gains `pace_status`, `gpa_needed_unweighted`,
`gpa_needed_weighted`, `target_letter_grade`, `target_cutoff_percent`,
`n_courses_below_target`, `courses_below_target` (a `string_agg` of course name
and current Y1 percent), `quickest_win_course`, `quickest_win_pace_percent`, and
`quickest_win_next_letter`. The roster is a Google Sheet, so the per-course
detail is summarized into strings at the student grain.

`rpt_tableau__gpa_goal_progress` gains `pace_status`, `gpa_needed_weighted`,
`target_letter_grade`, and `n_courses_below_target`, added to the select list
and the contract. The Monitor reads it on the current-year row.

A new `rpt_tableau__gpa_course_pace` carries the course-grain pace and quickest
win for a course-level view on the Monitor or the Gradebook rollup. It reads the
two course models and the enrollment roster.

`rpt_tableau__student_course_grades` gains `need_83`, derived from `need_60` and
`need_70` by the affine identity, so the Gradebook rollup can move its course
target from the B- cutoff to the B cutoff.

## Commitment log

Phase 2. A Google Form writes to a sheet with student number, meeting date,
course, committed percent, and advisor. The sheet is read as a
`sources-external.yml` entry and a `stg_google_sheets__gpa_commitments` model,
following the GPA goals tab. `int_gpa__commitment_outcomes` joins each
commitment to the course's Y1 percent as of the commitment date, from the daily
snapshot `snapshot_powerschool__gpa_term` where available and otherwise from the
live value at the next meeting, and to the current value. The roster gains
`last_commitment_course`, `last_commitment_percent`,
`last_commitment_percent_then`, and `last_commitment_percent_now`.

The target and quickest win are frozen in the log at commitment time, not in the
live models.

## Leader rollup

Phase 2. `rpt_tableau__gpa_pace_rollup` at school, grade, and advisory grain:
students by `pace_status`, commitments logged and hit, and the course that is
the quickest win for the most students. Small-cell suppression is not automated
(#4237), so the grain stops at advisory and no demographic cut is added here.

## Edge rules

- Scale 874 and any unresolvable `courses_gradescaleid_unweighted` yield
  `unknown`, never a wrong letter.
- `remaining_weight` of 0 yields a null pace; the course is `is_locked`.
- The F* to F step has 0 points gained and 0 gap. `need_gap` is floored at 1.0
  and `points_gained` of 0 excludes the course from ranking.
- Negative `gpa_needed_unweighted` is a valid value meaning already secured.
- A dropped course is already absent from `base_powerschool__final_grades`.
- A student withdrawn mid-year keeps their rows; the Monitor's population filter
  handles them.

## Verification

Unit tests per model with fixtures covering: no weighted courses; one AP and one
honors course; a locked ended course; a course with exams; needed above the
scale max; needed at or below 0; an unresolvable scale; a student with no graded
course yet.

Back-tests on a dev build:

- Plugging each student's `pace_percent` into every remaining term of every
  unlocked course yields a credit-weighted unweighted Y1 GPA at or above
  `gpa_needed_unweighted` for every student with a computable pace.
- `gpa_needed_weighted − gpa_needed_unweighted` equals `schedule_bump` for every
  row, by construction, and `schedule_bump` matches the AY2025 stored-grade
  check when run against last year.
- `need_83` equals the affine derivation within 0.01 for every row.
- No `pace_status` of `unknown` for a student with a resolvable schedule.

CI builds kipptaf, so these models are exercised by dbt Cloud CI, unlike the
#5756 fix.

## Rollout

| When               | What                                                                               |
| ------------------ | ---------------------------------------------------------------------------------- |
| Week of 2026-10-13 | Phase 1: the three intermediates, roster and Monitor columns, `need_83`.           |
| 2026-11-02         | Q2 opens. Roster live with Q2 pace. Tableau label changes land in the same window. |
| Before December    | Phase 2: commitment log and leader rollup.                                         |
| When #5761 merges  | Needed GPA corrects for seniors; the target letter follows with no change here.    |

Until #5761 merges, the target letter runs about one letter step high for most
seniors. The models read the same column, so no code change is needed when the
fix lands.

## Open questions

- Whether the roster should show `pace_percent` per course as a string column or
  only the summary. The sheet is read by advisors on a laptop; a long string may
  not help.
- Whether the Monitor's course-level view belongs on the Monitor or on the
  Gradebook rollup, which already has the course grain.
- Exam-term handling: pace applies to exams as written. A quarter-only pace
  under an assumed exam score is a possible revision.

## Revision 2026-10-07, from review of PR #5773

- Names. `int_gpa__student_quarter_target` is
  `int_powerschool__student_y1_target` and `int_gpa__course_quarter_pace` is
  `int_powerschool__course_pace`. Neither model has a quarter grain: the target
  is a Y1 letter and the pace is the percent needed in every remaining term
  through year end. `rpt_tableau__gpa_course_pace` keeps its name.
- `int_gpa__course_quickest_win` is folded into `int_powerschool__course_pace`
  as columns (`next_letter_grade`, `next_cutoff_percent`, `next_grade_points`,
  `points_gained`, `pace_percent_to_next`, `need_gap`, `score`,
  `quickest_win_rank`). It shared the pace model's grain and only input, and
  every consumer joined it back one-to-one.
- `pace_status` reads `on_pace` when every open course that has started is
  graded and none sits below target. A course that has not started yet, such as
  a spring-semester course in the fall, neither blocks nor counts. The earlier
  rule, which waited for every course to carry a grade, held every student with
  a spring course at `not_on_pace` all fall.
- `schedule_bump` is averaged over the open credits, the same base
  `gpa_needed_unweighted` is averaged over, so `gpa_needed_weighted` is the
  weighted average needed in the open courses. Locked courses are outside both.
- The edge rule for other scales is implemented: an open course whose unweighted
  grade scale is not the 2019 reference scale by name, or resolves to nothing,
  makes the status `unknown` and nulls the target and needed GPA. Every
  unweighted scale on a current HS GPA course today is the 2019 scale (Newark
  and Camden on id 976; Paterson's id 487 is the same scale and has no high
  school students), so the rule fires on nothing yet.
- `pace_status` is the source for the "percent on pace" goal type that #4581
  planned and `int_gpa__goal_student_metrics` still stubs as NULL under
  `TODO(#4581)`. The mapping is `is_on_pace = pace_status = 'on_pace'` and
  `is_on_pace_denominator = pace_status in ('on_pace', 'not_on_pace')`, the
  students for whom a 3.0 is still reachable; `goal_not_attainable` and
  `unknown` fall outside the denominator. Phase 2 wires those two columns from
  `int_powerschool__student_y1_target` and drops the separate
  `rpt_tableau__gpa_pace_rollup` in favor of the existing goal aggregations, so
  there is one on-pace rollup.
- Both models move into the `powerschool` package as
  `int_powerschool__student_y1_target` and `int_powerschool__course_pace`, built
  per NJ district and unioned in kipptaf by the usual `union_relations` wrapper,
  beside `int_powerschool__gpa_cumulative`. Every input is a package model, and
  the per-district grade scale lookup has one row per letter, so the
  `select distinct` projections the kipptaf copies needed are gone.
