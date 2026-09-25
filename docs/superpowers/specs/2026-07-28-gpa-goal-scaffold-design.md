# GPA Goal Scaffold — Design

Issue: [#4581](https://github.com/TEAMSchools/teamster/issues/4581)

## Problem and motivation

The GPA/gradebook dashboard needs goals for several GPA metrics
(`% of students at weighted Y1 GPA >= 3.0`,
`% at unweighted cumulative GPA >= 3.0`, `% on pace`, etc.) defined at mixed
grains — org, region, school, and each of those crossed with grade. Today there
is no goal layer for this dashboard: the `rpt_tableau__student_course_grades`
extract carries per-student detail but no targets, and the topline cascade's
goal system serves a different dashboard.

Goals are aggregate rates (a percentage of a cohort), so they must be joined
where the metric is aggregated to a grain — **upstream, in an intermediate
model, not in the reporting view**. This builds a dedicated goal scaffold for
the GPA dashboard, modeled on the proven topline aggregate-goals pattern
(`int_google_sheets__topline_aggregate_goals` +
`int_topline__dashboard_aggregations`) but decoupled from it.

## Non-goals / out of scope

- The topline cascade dashboard's goals (unchanged; GPA remains a topline metric
  there independently).
- Setting the actual goal values for AY2026 (tracked locally; a separate
  analysis).
- Attaching goals to per-student rows — rejected in favor of pre-aggregation
  (rationale in _Architecture_).
- The per-student `is_on_pace_cumulative_3_0` / `gpa_y1_weighted_target` extract
  columns — a separate follow-on off the merged #4528/#4529 work, consumed here.

## Goals-source sheet

Ops maintains a Google Sheet (already created, blank). One row per goal.

| #   | column          | type    | required               | notes                                                                                                                                 |
| --- | --------------- | ------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `academic_year` | int     | yes                    | year the goal applies (`2026` = SY26-27); goals are year-scoped so history is retained                                                |
| 2   | `org_level`     | string  | yes                    | `org` / `region` / `school` — the scope grain                                                                                         |
| 3   | `region`        | string  | region + school rows   | region name; blank for `org`                                                                                                          |
| 4   | `schoolid`      | int     | school rows only       | PowerSchool school number; blank otherwise                                                                                            |
| 5   | `grade_low`     | int     | yes                    | low grade of the band                                                                                                                 |
| 6   | `grade_high`    | int     | yes                    | high grade of the band (equal to `grade_low` for a single grade)                                                                      |
| 7   | `metric`        | string  | yes                    | which per-student measure: `y1_gpa_weighted`, `y1_gpa_unweighted`, `cumulative_gpa_unweighted`, `on_pace` (enumerated; extend in dbt) |
| 8   | `threshold`     | numeric | threshold metrics only | the cutoff, e.g. `3.0`; blank for `on_pace`                                                                                           |
| 9   | `direction`     | string  | yes                    | student-level comparison — `>=` (default) or `<=`                                                                                     |
| 10  | `goal`          | numeric | see below              | target as a whole-number percent (`49`, `58`); dbt normalizes to a proportion                                                         |

An optional free-text `notes` column is ignored by dbt.

### Grain encoding

| Grain          | `org_level` | `region` | `schoolid` | `grade_low`–`grade_high` |
| -------------- | ----------- | -------- | ---------- | ------------------------ |
| org            | `org`       | (blank)  | (blank)    | 9–12                     |
| org + grade    | `org`       | (blank)  | (blank)    | 10–10                    |
| region         | `region`    | Newark   | (blank)    | 9–12                     |
| region + grade | `region`    | Newark   | (blank)    | 10–10                    |
| school         | `school`    | Newark   | 73253      | 9–12                     |
| school + grade | `school`    | Newark   | 73253      | 10–10                    |

A single grade is `grade_low = grade_high`; all grades is the full band. Grade
granularity is driven entirely by the row — the metric aggregation does not
enumerate grades; each goal row picks up the students its band matches (the
topline mechanism).

## Metric shapes

Two shapes, distinguished by `metric`:

1. **Threshold metrics** (`y1_gpa_weighted`, `y1_gpa_unweighted`,
   `cumulative_gpa_unweighted`): numerator = students whose measure satisfies
   `measure {direction} threshold`; denominator = all students in the grain.
   Threshold and direction come from the sheet, so Ops can add a `>= 3.5` or
   `>= 2.0` goal without a code change.
1. **Subset-denominator metric** (`on_pace`): numerator = on-pace students;
   denominator = the **priority subset** (attainable and needs-to-move), a
   per-student determination — not all students in the grain. Ignores
   `threshold` / `direction`. Its numerator and denominator flags are computed
   upstream (fed by the merged `is_on_pace_cumulative_3_0` / attainability
   work). `on_pace` is the one place this scaffold diverges from topline.

## Direction and goal evaluation

One direction column, per the requirement. `direction` is the **student-level**
comparison (the `>=` in `% >= 3.0`), defaulting to `>=`. The **goal-level**
direction (do we want the resulting percentage high or low) is _derived_, not a
second column: `>=` / `>` implies higher-is-better; `<=` / `<` implies
lower-is-better. From that, the aggregation computes:

```text
is_goal_met      = higher_is_better ? (rate >= goal) : (rate <= goal)
progress_to_goal = higher_is_better ? least(1, rate / goal)
                                    : least(1, goal / rate)   -- guarded for rate = 0
```

`goal` is blank-allowed for a monitor-only metric (e.g. `on_pace` if it carries
no fixed target — open decision below): a null `goal` yields null `is_goal_met`
/ `progress_to_goal`, and the rate still displays.

## Architecture

Data flow (each arrow is a model):

```text
Google Sheet (goals)
  -> stg_google_sheets__gpa_goals        (external source, contract, key-not-null filter)
  -> int_google_sheets__gpa_goals        (add grade_band + aggregation_hash; normalize goal to proportion; derive higher_is_better)

GPA per-student measures (existing int_powerschool__gpa_* family, + on-pace flags)
  -> int_gpa__goal_student_metrics       (one row per academic_year x region x schoolid x grade_level x student; raw measures + on_pace num/denom flags)

int_gpa__goal_student_metrics + int_google_sheets__gpa_goals
  -> int_gpa__goal_aggregations          (roll up to each grain, join goals, compute rate + is_goal_met + progress)
  -> rpt_tableau__gpa_goals              (reporting view the dashboard's scoreboard/progress tiles read)
```

`rpt_tableau__student_course_grades` stays the per-student **detail/drill-down**
source; this scaffold sits beside it (the topline `student_metrics` vs
`dashboard_aggregations` split). Proposed directory: goal staging under
`models/google/sheets/`; the two new GPA ints under a new
`models/gpa/intermediate/`; the rpt under `models/extracts/tableau/` (directory
placement is a minor open decision).

### `int_google_sheets__gpa_goals`

Mirrors `int_google_sheets__topline_aggregate_goals`: derives `grade_band` and
an `aggregation_hash` that encodes the grain (`org` | `region` | `schoolid`,
plus grade band), normalizes `goal` to a 0–1 proportion, and derives
`higher_is_better` from `direction`.

### `int_gpa__goal_student_metrics`

One row per (`academic_year`, `region`, `schoolid`, `grade_level`, `studentid`)
carrying the raw measures needed by the threshold metrics (`y1_gpa_weighted`,
`y1_gpa_unweighted`, `cumulative_gpa_unweighted` projected) plus the two
`on_pace` flags (`is_on_pace`, `is_on_pace_denominator`). Sourced from the
`int_powerschool__gpa_*` family; exact upstream columns finalized in the plan
against current models. This is the analog of `int_topline__student_metrics`.

### `int_gpa__goal_aggregations`

Follows `int_topline__dashboard_aggregations`: a `UNION ALL` of one block per
`org_level` (org / region / school). Each block groups the student metrics to
its grain and left-joins the goals on
`grade_level between grade_low and grade_high` plus the org-level key match. Per
grouped goal row it computes:

- threshold metric rate: direction-aware numerator over grain count —
  `safe_divide(countif((direction = '>=' and measure >= threshold) or (direction = '<=' and measure <= threshold)), count(student))`
- `on_pace` rate:
  `safe_divide(countif(is_on_pace and is_on_pace_denominator), countif(is_on_pace_denominator))`
- then `is_goal_met` / `progress_to_goal` from _Direction and goal evaluation_.

The join is goal-driven (a grain shows in this model when it has a goal row);
the detail extract covers ad-hoc grains without a goal.

### Reporting + exposure

`rpt_tableau__gpa_goals` is a thin contracted view over the aggregation. The GPA
dashboard that consumes it gets a dbt exposure in `models/exposures/tableau.yml`
(kipptaf convention: every external consumer has an exposure).

## Testing

- `stg_google_sheets__gpa_goals`: contract; `where` key-not-null filter for the
  Sheet's phantom empty rows; `accepted_values` on `org_level`, `metric`,
  `direction`; `expression_is_true` `goal between 0 and 100`; grade_low <=
  grade_high.
- `int_google_sheets__gpa_goals`: `unique_combination_of_columns` on
  (`academic_year`, `metric`, `aggregation_hash`).
- `int_gpa__goal_student_metrics`: unique on (`academic_year`, `schoolid`,
  `studentid`).
- `int_gpa__goal_aggregations` / `rpt_tableau__gpa_goals`: unique on
  (`academic_year`, `metric`, `aggregation_hash`); contract on the rpt.
- Unit test on the aggregation covering: a threshold metric at each org_level, a
  single-grade vs all-grades band, a `<=` direction, and the `on_pace`
  subset-denominator path.

## Dependencies

- Merged #4528 / #4529 (unweighted needed-Y1 + attainability) — feeds the
  `on_pace` flags once district prod rebuilds.
- The per-student `is_on_pace_cumulative_3_0` extract column (follow-on) — its
  logic is the numerator flag; the priority-subset definition supplies the
  denominator flag.

## Open decisions

1. Does `on_pace` carry a numeric `goal`, or is it monitor-only (null goal,
   rate-only)? Scaffold supports both; needs the stakeholder call.
1. The priority-subset (`is_on_pace_denominator`) definition is still the
   working hypothesis pending Sharba — the scaffold treats it as a swappable
   upstream flag, not hardcoded logic.
1. Final Sheet column names/casing — confirm against the blank sheet's header
   row before the staging model (Google Sheets staging inherits header case).
1. Directory placement of the two new GPA ints (`models/gpa/` vs
   `models/reporting/`).

## Rollout / sequencing

1. Wire the Sheet as a `google_sheets` external source + `stg_` + `int_` goals
   models (needs the confirmed header row).
1. Build `int_gpa__goal_student_metrics` from the GPA int family (after the
   on-pace flags land in prod).
1. Build `int_gpa__goal_aggregations` + `rpt_tableau__gpa_goals` + exposure.
1. Populate the Sheet with AY2026 goals (the separate goal-setting analysis) and
   validate the scaffold end to end.
