# Truancy and formative assessment grain — design

Refs [#5381](https://github.com/TEAMSchools/teamster/issues/5381).

Covers `int_topline__truancy_weekly` and
`int_topline__formative_assessment_weekly`, the last 2 models on #5381 that need
a code change. The others have their own specs; `star_assessment_weekly` needs
an Ops fix, not code.

## Problem

Both models repeat a key that `int_topline__student_metrics` scores once per
row, so a repeated student outweighs one that appears once.

Measured against prod on 2026-09-17:

| Model                                      | Grain tested                     | Keys    | Duplicated | Disagreeing |
| ------------------------------------------ | -------------------------------- | ------- | ---------- | ----------- |
| `int_topline__truancy_weekly`              | student-week                     | 861,248 | 23         | 2           |
| `int_topline__formative_assessment_weekly` | student-week-discipline-strategy | 74,210  | 46         | 0           |

Different causes, one spec because both are small, both are the last of the set,
and both touch `int_topline__student_metrics`.

### `int_topline__truancy_weekly` groups by a column nobody reads

The model's `group by` carries `schoolid`, so a student enrolled at 2 schools in
one week gets 2 rows. All 23 duplicated student-weeks are exactly that, and 2 of
them disagree on `is_truant_int`.

`schoolid` is not part of the grain downstream. `int_topline__student_metrics`
reads this model at lines 359-373 and projects `student_number`,
`academic_year`, the 2 week columns, and `is_truant_int` — `schoolid` is never
selected, so the 2 rows are indistinguishable to every consumer.

### `int_topline__formative_assessment_weekly` joins below its own grain

The model joins `int_assessments__response_rollup` on `student_number`,
`academic_year`, `discipline`, and a week window. That model is one row per
**assessment**, so a student who sits 2 different assessments in the same
discipline inside one week gets 2 rows.

All 46 duplicated keys are that case, all in AY2025, and all 46 pairs share
`administered_at` and `module_type` while differing in `subject_area` or `title`
— 2 distinct assessments given the same day.

The spine is not involved. `int_extracts__student_enrollments_subjects_weeks`
contributes 0 of the 46, so this change does not depend on the spine dedupe
tracked separately.

There is a second defect on the same rows. `mastery_as_of_week` is a
`last_value(...) over (... order by sw.week_start_monday)` with the default
`RANGE` frame, so every row sharing a `week_start_monday` is a peer and sits
inside the frame. Which peer `last_value` returns is unspecified, so the value
each duplicated key reports today is arbitrary. It happens not to bite — both
rows of all 46 pairs carry the same value — because both read the same frame.

## Design

### `int_topline__truancy_weekly`

Drop `schoolid` from the select list and the `group by`.

```sql
select
    student_number,
    academic_year,
    week_start_monday,
    week_end_sunday,

    max(if(is_truant, 1, 0)) as is_truant_int,
from {{ ref("int_students__attendance_daily") }}
where academic_year >= {{ var("current_academic_year") - 1 }}
group by student_number, academic_year, week_start_monday, week_end_sunday
```

`max(if(is_truant, 1, 0))` already collapses the day grain, so it collapses the
school grain identically: truant on any day at any school is truant that week.
That is the right reading for a student-level weekly indicator — a student does
not become less truant by transferring mid-week.

### `int_topline__formative_assessment_weekly`

Rank the responses inside the week and keep the latest.

```sql
with
    responses_discipline as (
        select
            powerschool_student_number,
            academic_year,
            module_type,
            title,
            administered_at,
            discipline,

            case
                when is_mastery then 1 when not is_mastery then 0 else -1
            end as is_mastery_int,
        from {{ ref("int_assessments__response_rollup") }}
        where
            response_type = 'overall'
            and module_type in ('QA', 'MQQ', 'CRQ')
            and academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    assessment_weeks as (
        select
            sw.student_number,
            sw.academic_year,
            sw.week_start_monday,
            sw.week_end_sunday,
            sw.discipline,

            rr.title,
            rr.administered_at,
            rr.is_mastery_int,

            case
                when rr.module_type in ('QA', 'MQQ')
                then 'All'
                when rr.module_type = 'CRQ' and sw.region = 'Miami'
                then 'Florida'
            end as formative_strategy,
        from {{ ref("int_extracts__student_enrollments_subjects_weeks") }} as sw
        left join
            responses_discipline as rr
            on sw.student_number = rr.powerschool_student_number
            and sw.academic_year = rr.academic_year
            and sw.discipline = rr.discipline
            and rr.administered_at between sw.week_start_monday and sw.week_end_sunday
        where
            sw.is_enrolled_week
            and sw.academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    assessment_weeks_ranked as (
        select
            student_number,
            academic_year,
            week_start_monday,
            week_end_sunday,
            discipline,
            formative_strategy,
            is_mastery_int,

            row_number() over (
                partition by
                    student_number,
                    academic_year,
                    week_start_monday,
                    discipline,
                    formative_strategy
                order by administered_at desc, title desc
            ) as rn,
        from assessment_weeks
        where formative_strategy is not null
    )

select
    student_number,
    academic_year,
    week_start_monday,
    week_end_sunday,
    discipline,
    formative_strategy,

    if(is_mastery_int = -1, null, is_mastery_int) as is_mastery_running_int,
from assessment_weeks_ranked
where rn = 1
```

Four things in that shape are deliberate.

The `title` tie-break is what makes the pick deterministic. `administered_at`
alone ties on exactly these 46 pairs, which is the same ambiguity the
`last_value` frame has today — ordering by a column that ties does not resolve
anything.

`where formative_strategy is not null` moves into the CTE that computes `rn`'s
input, not the one that filters on it. Ranking before the filter would let
`rn = 1` land on a row the filter then drops, losing the key entirely — a
student with a non-Miami CRQ and a QA in the same discipline-week would lose the
QA row. `.claude/rules/dbt-sql.md` names this trap directly for the
ranked-column form.

`formative_strategy` joins the `partition by`. It is part of the output grain,
so a student with both an `All` row and a `Florida` row in one discipline-week
must keep both.

The `last_value` window is deleted. Under
`where formative_strategy is not null`, every surviving row has a response, so
the frame's last non-null value is always the current week's own — the
carry-forward is a no-op that cannot fire. Verified against prod: computing the
value from the row reproduces the window's output on every non-duplicated key.
Deleting it also removes the arbitrary-peer ambiguity rather than relying on the
dedupe to hide it.

The output column keeps the name `is_mastery_running_int` because
`int_topline__student_metrics` reads it by name. The name is inaccurate and has
been — see the owner question below.

### `int_topline__student_metrics`

Line 94 filters `formative_strategy = 'Miami'`. The model emits `'All'` or
`'Florida'`, never `'Miami'`, so the Miami formative branch selects 0 rows.
Change the literal to `'Florida'`.

This moves nothing today. `'Florida'` requires a Miami CRQ response, and no
Miami student has ever taken one — 0 of the 7,683 students with a CRQ response
across AY2025 and AY2026 are Miami. Fixing the literal anyway is what keeps the
indicator from staying silently empty on the day Miami CRQ data arrives.

The empty branch itself is an Ops question, not a code one, and is recorded on
#5381 rather than fixed here.

### Properties

Both files carry only `materialized: table` and a cron comment today — no
description, no columns, no tests. Both gain:

- `dbt_utils.unique_combination_of_columns` at `config: severity: error`. The
  kipptaf project default is `warn`, which would not fail CI, and these are
  silent double-count defects.
  - `truancy_weekly`: `student_number`, `academic_year`, `week_start_monday`.
  - `formative_assessment_weekly`: those 3 plus `discipline` and
    `formative_strategy`.
- A model description and a description per column, matching the shape
  `int_topline__gpa_term_weekly.yml` uses on `main`.

The existing `materialized: table` and `cron_schedule: 0 0 * * *` stay
untouched.

## Measured shift

Simulated by running both the current and the fixed logic over the same upstream
data in one query, so the prod table's build lag cancels out.

`int_topline__truancy_weekly`, AY2026:

| Measure      | Now     | Fixed   |
| ------------ | ------- | ------- |
| Rows         | 441,115 | 441,099 |
| Truancy rate | 1.2632% | 1.2614% |

`int_topline__formative_assessment_weekly`:

| Measure                      | Now      | Fixed    |
| ---------------------------- | -------- | -------- |
| AY2025 rows                  | 73,451   | 73,405   |
| AY2025 Formative Assessments | 48.0333% | 47.9857% |
| AY2026 rows                  | 807      | 807      |
| AY2026 Formative Assessments | 26.3941% | 26.3941% |

AY2026 does not move at all: every one of the 46 duplicates is in AY2025.
Neither change is large. Both are correctness fixes that also remove a
non-deterministic result, not rate corrections.

## Question for the metric owner

`is_mastery_running_int` does not run, and has not.

The carry-forward window was written to hold a student's last known mastery
across weeks with no assessment. But `where formative_strategy is not null`
drops every week without a response — a week with no assessment has a null
`module_type`, so its `formative_strategy` is null — so no carried-forward row
ever reaches the output. Each surviving row reports only its own week's result.

Two readings, and the owner picks:

1. The indicator is meant to be per-week. Then the current output is correct and
   the column should be renamed, since `_running` describes something the model
   does not do.
2. The indicator is meant to carry forward. Then the filter is the bug, the
   output is missing every no-assessment week, and the fix is a larger change
   than this one.

This spec assumes reading 1 and changes nothing about it. Recorded on #5381.

## Verification

- `uv run dbt build --select int_topline__truancy_weekly int_topline__formative_assessment_weekly int_topline__student_metrics --project-dir <worktree>/src/dbt/kipptaf`
- The issue's duplicate-key query against prod for both models: `duplicated`
  must reach 0 and `max_rows` 1.
- Re-run the shift simulation after the build and confirm it matches the tables
  above, so the published numbers in the PR body are the ones that shipped.
- Confirm the `'Florida'` literal change still selects 0 rows, so the edit is
  provably inert today.
- `trunk check --force --no-fix` on all 5 changed files.

## Out of scope

`int_assessments__response_rollup`'s own grain. It is per assessment on purpose
and has other consumers; the topline is the model reading it at the wrong grain,
so the collapse belongs in the topline.

`int_extracts__student_enrollments_subjects_weeks`. It contributes 0 duplicates
to this model, and its own dedupe is tracked separately.

Why Miami has no CRQ responses. That is an Ops data question, recorded on #5381.
