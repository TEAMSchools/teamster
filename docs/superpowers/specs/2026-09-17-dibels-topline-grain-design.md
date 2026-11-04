# DIBELS topline grain fan-out — design

Refs [#5381](https://github.com/TEAMSchools/teamster/issues/5381).

Covers `int_topline__dibels_pm_weekly` and
`int_topline__dibels_benchmark_weekly`. The other models on #5381 have different
causes and get their own changes.

## Problem

Both models repeat a student-week, and `int_topline__student_metrics` scores
each row, so a repeated student outweighs one that appears once. Three topline
indicators read these 2 models: DIBELS PM, DIBELS PM Fidelity, and DIBELS
Benchmark Proficiency.

Measured against prod on 2026-09-17:

| Model                                  | Rows   | Duplicated student-weeks | Most rows on one key |
| -------------------------------------- | ------ | ------------------------ | -------------------- |
| `int_topline__dibels_pm_weekly`        | 50,850 | 18,260                   | 4                    |
| `int_topline__dibels_benchmark_weekly` | 62,914 | 38                       | 2                    |

The 2 models fan out for different reasons.

### `int_topline__dibels_pm_weekly` reads a measure-grain model

The model selects `met_pm_round_overall_criteria` and `completed_test_round_int`
— both round-level verdicts — off `int_amplify__pm_met_criteria`, which is one
row per student per round per **measure**. A student assessed on 4 measures in a
round gets 4 identical rows per week.

It is only the measure grain. The overlapping PM windows in
`int_amplify__pm_met_criteria` belong to different grade bands, and no student
crosses a band mid-year: a student-week matching 2 distinct rounds occurs 0
times across AY2025 and AY2026.

### `int_topline__dibels_benchmark_weekly` repeats on a grade change

`int_amplify__all_assessments` is keyed partly on `assessment_grade_int`, the
grade recorded at the time of the assessment. When a student's grade changes
inside one LITEX window, the model's join — `student_number`, `academic_year`,
`period` — matches both the old-grade and the new-grade row.

2 student-periods do this, producing the 38 duplicated student-weeks. Both carry
the same `is_proficient_int` on either row, so the fan-out double-weights those
students without changing the value they report.

## Design

### `int_topline__dibels_pm_weekly`

Collapse `int_amplify__pm_met_criteria` to the join key before joining:

```sql
with
    pm_rounds as (
        select
            student_number,
            academic_year,
            start_date,
            end_date,

            min(met_pm_round_overall_criteria) as met_pm_round_overall_criteria,
            min(completed_test_round_int) as completed_test_round_int,
        from {{ ref("int_amplify__pm_met_criteria") }}
        where academic_year >= {{ var("current_academic_year") - 1 }}
        group by student_number, academic_year, start_date, end_date
    )

select
    cw.student_number,
    cw.academic_year,
    cw.week_start_monday,
    cw.week_end_sunday,

    dp.met_pm_round_overall_criteria,
    dp.completed_test_round_int,
from {{ ref("int_extracts__student_enrollments_weeks") }} as cw
inner join
    pm_rounds as dp
    on cw.student_number = dp.student_number
    and cw.academic_year = dp.academic_year
    and cw.week_start_monday between dp.start_date and dp.end_date
where cw.academic_year >= {{ var("current_academic_year") - 1 }}
```

`min()` rather than `any_value()`, and the choice is load-bearing. The round
verdict is not constant across measures on 40 student-weeks, all in AY2025,
where `int_amplify__pm_met_criteria` mixes measures whose `pm_goal_criteria` is
`AND` with measures whose criteria is null (read as OR). `min()` gives the `AND`
reading — a round counts as met only when every measure met it — which is what
T&L made the network-wide rule for SY26-27. `any_value()` would pick arbitrarily
on those 40.

`BETWEEN` on the round window stays. The windows do not abut or overlap within a
grade band, and the boundary rule in `.claude/rules/dbt-sql.md` calls `BETWEEN`
correct for non-overlapping windows. This is not the #5375 snapshot shape; no
validity timestamps are involved.

### `int_topline__dibels_benchmark_weekly`

Rank the assessment rows and prefer the one recorded at the student's enrolled
grade, matching how `rpt_tableau__dibels_dashboard` resolves the same collision:

```sql
with
    composite_weeks as (
        select
            cw.student_number,
            cw.academic_year,
            cw.week_start_monday,
            cw.week_end_sunday,

            amp.aggregated_measure_standard_level,

            row_number() over (
                partition by
                    cw.student_number, cw.academic_year, cw.week_start_monday
                order by if(amp.assessment_grade_int = cw.grade_level, 0, 1) asc
            ) as rn,
        from {{ ref("int_extracts__student_enrollments_weeks") }} as cw
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on cw.academic_year = rt.academic_year
            and cw.region = rt.city
            and cw.week_start_monday between rt.start_date and rt.end_date
            and rt.type = 'LITEX'
        left join
            {{ ref("int_amplify__all_assessments") }} as amp
            on cw.student_number = amp.student_number
            and cw.academic_year = amp.academic_year
            and rt.name = amp.period
            and amp.measure_name = 'Composite'
        where
            cw.academic_year >= {{ var("current_academic_year") - 1 }}
            and cw.grade_level <= 8
    )

select
    student_number,
    academic_year,
    week_start_monday,
    week_end_sunday,

    case
        when aggregated_measure_standard_level = 'At/Above'
        then 1
        when aggregated_measure_standard_level = 'Below/Well Below'
        then 0
    end as is_proficient_int,
from composite_weeks
where rn = 1
```

The ranked-column form rather than `dbt_utils.deduplicate`, because the
tie-break compares a column on each side of the join (`amp.assessment_grade_int`
against `cw.grade_level`) and the macro can only order within one relation.

The `LEFT JOIN` to `int_amplify__all_assessments` stays a left join. A student
enrolled in a LITEX week with no Composite score keeps a row with a null
`is_proficient_int`, which is what the model does today.

The `amp.measure_name = 'Composite'` filter stays. It is what keeps PM rows out
of this model — verified, 0 `model_type` variation reaches it.

### Properties

Neither `int_topline__dibels_pm_weekly.yml` nor
`int_topline__dibels_benchmark_weekly.yml` carries a description, columns, or
tests today. Both gain:

- `dbt_utils.unique_combination_of_columns` on `student_number`,
  `academic_year`, `week_start_monday`, at `config: severity: error`. The
  kipptaf project default is `warn`, which would not fail CI, and this is a
  silent double-count defect.
- A model description and a description per column, matching the shape
  `int_topline__gpa_term_weekly.yml` uses on `main`.

The existing `materialized: table` and `cron_schedule: 0 0 * * *` stay
untouched.

## DIBELS reference updates

`.claude/skills/dibels-dashboard/SKILL.md` requires that any DIBELS change
update both the skill and `docs/models/dibels-dashboard-data-model.md`. Three
findings from this work land there:

1. `int_amplify__pm_met_criteria` is measure grain, and its round-level columns
   (`met_pm_round_overall_criteria`, `completed_test_round_int`) repeat per
   measure. Any consumer reading them at round grain must aggregate first.
2. The round verdict is not constant across measures on 40 AY2025 student-weeks,
   where `pm_goal_criteria` mixes `AND` and null. The topline reads the `AND`
   interpretation.
3. The skill's stated reason that `int_topline__dibels_benchmark_weekly` is
   `model_type`-safe is wrong. It says the model filters
   `measure_standard = 'Composite'`; the SQL filters `measure_name`. The filter
   does exclude PM rows, so the conclusion holds and the justification does not.

## Measured shift

Simulated against prod by running each model's fixed SQL and comparing to the
live table.

`int_topline__dibels_pm_weekly`:

| Measure                  | Now    | Fixed  |
| ------------------------ | ------ | ------ |
| Rows                     | 50,850 | 22,742 |
| Duplicated student-weeks | 18,260 | 0      |

`int_topline__dibels_benchmark_weekly`:

| Measure                  | Now    | Fixed  |
| ------------------------ | ------ | ------ |
| Rows                     | 62,914 | 62,876 |
| Duplicated student-weeks | 38     | 0      |

Published indicators on `int_topline__student_metrics`:

| Indicator          | Now    | Fixed  |
| ------------------ | ------ | ------ |
| DIBELS PM          | 15.02% | 18.04% |
| DIBELS PM Fidelity | 95.29% | 93.91% |

Over half of `int_topline__dibels_pm_weekly` was duplicate rows, and the
duplicates were not evenly spread — a student assessed on more measures carried
more weight, so the PM rate moves 3 points.

DIBELS Benchmark Proficiency does not move at all. Both rows of each duplicated
pair already carried the same `is_proficient_int`, so dropping one changes no
rate — the fix removes a double-weighting, not a wrong value.

## Verification

- `uv run dbt build --select int_topline__dibels_pm_weekly int_topline__dibels_benchmark_weekly --project-dir <worktree>/src/dbt/kipptaf`
- The issue's duplicate-key query against prod for both models: `duplicated`
  must reach 0 and `max_rows` 1.
- Re-run the shift simulation after the build and confirm it matches the tables
  above, so the published numbers in the PR body are the ones that shipped.
- `trunk check --force --no-fix` on every changed file.

## Out of scope

`int_amplify__pm_met_criteria`'s own grain. Collapsing it upstream would be the
smaller diff here but a wider blast radius — `rpt_tableau__dibels_dashboard`
reads it at measure grain deliberately, and the dashboard needs the per-measure
rows. The topline is the consumer reading it at the wrong grain, so the topline
is where the aggregate belongs.

The remaining #5381 models: `truancy_weekly`, `formative_assessment_weekly`'s
residual, `star_assessment_weekly`, and the
`int_extracts__student_enrollments_subjects_weeks` spine. Diagnoses recorded on
#5381.
