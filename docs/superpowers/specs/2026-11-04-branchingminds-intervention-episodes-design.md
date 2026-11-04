# Branching Minds intervention assignment episodes — design

Issue: [#6269](https://github.com/TEAMSchools/teamster/issues/6269)

## Intent

Answer "is this student assigned to intervention X right now?" and "when was the
student assigned to it?" from Branching Minds (BrM) data. The first consumer is
a yes or no on SIPPS per student. The BrM export is 1 row per plan, and plans
overlap and run in cycles, so a plan-level read makes the boolean ambiguous.
This model collapses plans into dated assignment spans.

## Goals

- 1 row per student, intervention, and continuous assignment span (an
  "episode"), with `episode_start`, `episode_end`, and `is_current`.
- Every intervention in BrM, not only SIPPS. Consumers filter on
  `intervention_name`.
- A span survives BrM's fiscal-year rollover: staging already keeps the newest
  partition per plan, so a plan that ran across years appears once.

## Non-goals

- Dosage, session delivery, goals, or progress monitoring. The brainstorm
  started there and was pared down to assignment status.
- Plan-level detail (setting, staff, minutes). It stays in
  `stg_branchingminds__intervention_plans`.
- A join to PowerSchool for region, school, or demographics. Consumers join on
  `student_number`.

## Anti-goals

- Treating `intervention_end_date` as an actual end. It is the planned end, and
  the export has no plan status column. The model must not invent an exit.
- A SIPPS-specific model. A second intervention would need a copy.

## Constraints

- Source: `stg_branchingminds__intervention_plans` (kipptaf). It has not built
  in prod: the BrM sensor is stopped and no asset has materialized. The only
  copy is `zz_stg_kipptaf_branchingminds` from the 2026-10-22 branch deployment.
  The model can ship before prod rollout; it carries no rows until the 9 BrM
  assets run and the externals are re-staged against prod.
- Layer: source `int_` under `models/branchingminds/intermediate/`. It changes
  grain, so the name takes a reshape suffix (A3):
  `int_branchingminds__intervention_plans_rollup`. The issue body names it
  `int_branchingminds__intervention_episodes`; the rollup name wins.
- The collapse is a pick over plans, allowed in a source `int_` (A5).
- Student-level rows, so `config.meta.contains_pii: true`.
- `qualify` is banned (S1); the running max is a window column in 1 CTE and the
  episode number a second window in the next.

## Approaches

- **A. Plan grain.** 1 row per plan with `is_current`. History is free, and
  uniqueness is the plan id. Rejected: a student with 2 overlapping plans
  returns 2 current rows, so the boolean consumer has to aggregate.
- **B. Episodes (chosen).** Merge overlapping or back-to-back plans for 1
  student and intervention into 1 dated span. "On SIPPS now" is a filter.
  Validated on the 2026-10-22 snapshot: 381 SIPPS students yield 381 episodes, 2
  episodes merge more than 1 plan, and against the Camden BOY SIPPS group roster
  (182 students), 174 read current; the 8 that do not are 3 stale or duplicate
  roster rows and 5 students with no plan in BrM.
- **C. Daily scaffold.** Student x date x intervention. Rejected: heavy for a
  boolean, and no day-level consumer exists.

## Design

Model `int_branchingminds__intervention_plans_rollup`:

1. From staging, take `student_number`, `intervention_name`,
   `intervention_subject_area`, `district`, `school_id`, `intervention_plan_id`,
   `intervention_start_date`, `intervention_end_date`. Drop rows with a null
   start date; they cannot be placed on a timeline.
2. Per `student_number` and `intervention_name`, order by start then end, and
   compute the running max of prior plans' end dates.
3. A plan opens a new episode when it has no prior plan, or its start is more
   than 1 day after that running max. A null end date on a prior plan counts as
   open-ended: it extends the episode.
4. Episode number is the running sum of the new-episode flag.
5. Group to the episode: `episode_start` = min start, `episode_end` = max end
   (null when any plan in the episode has a null end), `plans_in_episode`,
   `intervention_plan_ids` as an array, `school_id` and `district` from the
   latest-starting plan, `intervention_subject_area` likewise.
6. `is_current` = `current_date(local timezone)` is on or after `episode_start`
   and (`episode_end` is null or on or before `episode_end`).
7. Surrogate key `intervention_episode_key` from `student_number`,
   `intervention_name`, `episode_start`.

Tests: `unique` on `intervention_episode_key` and
`dbt_utils.unique_combination_of_columns` on `student_number`,
`intervention_name`, `episode_start`, both at `error`; `not_null` on
`student_number`, `intervention_name`, `episode_start` at `error`. A unit test
covers 4 cases: 2 overlapping plans merge, 2 back-to-back plans (end = next
start minus 1 day) merge, 2 plans with a gap split, and a null end date keeps
the episode open.

Description names the planned-end limit: a plan dropped early stays current to
its end date, and a gap between cycles reads as not current. On 2026-11-04 every
Newark and Paterson SIPPS plan had a planned end of 2026-10-27, so those
students read not current while Camden reads current through 2027-01-05.

## Left to the builder

- The exact `rows between` frame for the running max and whether BigQuery needs
  a sentinel for null ends inside `max()`.
- Whether `intervention_plan_ids` is worth the array column or a min and max
  pair is enough.
- Column order and descriptions per `.claude/rules/dbt-yaml.md`.

## Revision 2026-11-04: academic year in the grain, and replace `is_sipps`

Two changes after reviewing the consumers.

### Academic year joins the grain

`int_extracts__student_enrollments_subjects` is student x academic year x
subject, and its subject values (`Reading`, `Math`) are the same strings BrM
puts in `intervention_subject_area`. `dim_student_enrollments` is stint grain
within a year. An episode with no year cannot equi-join to either, and once
history accrues a span can cross July 1.

So the rollup splits a span at the fiscal-year boundary and carries
`academic_year` (the year the span sits in, as its start year, matching the
enrollment models). Grain becomes `student_number`, `intervention_name`,
`academic_year`, `episode_start`; the surrogate key and the uniqueness test take
all 4. A plan that starts in June and ends in September yields 2 rows, one per
year, with `plans_in_episode` counting the plan in both.

The stint-level FK to `dim_student_enrollments` is a date-range join on
enrollment data, so it stays out of this source `int_`. A consumer that needs it
joins `episode_start` half-open against entry and exit dates.

### `is_sipps` reads the rollup

`int_extracts__student_enrollments` derives `is_sipps` from enrollment in
PowerSchool course `SEM01099G1`. That course carried rows only for Camden in
AY2025; in AY2026 the flag is false for every student while BrM holds SIPPS
plans in 3 regions. 4 Tableau extracts read the flag (DIBELS, DDI, assessment,
i-Ready APM).

The `sip` join on `base_powerschool__course_enrollments` is removed. In its
place, a CTE projects the rollup to distinct `student_number` and
`academic_year` where `intervention_name` starts with `SIPPS` (SIPPS and SIPPS
Challenge both count; grain projection per S12), and the hub left-joins it on
student number and academic year. `is_sipps` keeps its meaning: assigned at any
point in that year. The column's description changes to say the source is
Branching Minds.

This is a clean cut. BrM's export holds the current year only, so the 279 Camden
students flagged in AY2025 read false after the change. Keeping them would need
a year-conditional branch on the old course join, which is the plumbing being
retired. The user chose the cut.

The hub is a domain `int_` reading a source `int_`, an allowed edge (A1). The
edit widens dbt Cloud CI to the hub's descendants; expected.

Rollout order: the hub change ships with the rollup in 1 PR, but `is_sipps`
carries no rows until the BrM assets run in prod and the externals are
re-staged. Until then the flag is false everywhere, which is also its state
today.

## Revision 2026-11-04 (review): 2 PRs, and 4 rules the review added

The rollout paragraph above was wrong. The hub's prod automation condition
requires every dependency to have materialized, so a hub that reads the rollup
stops rebuilding until the BrM assets run in prod, and about 100 assets
downstream of it freeze with it. The work therefore ships as 2 PRs: the rollup
alone first (#6270), then the `is_sipps` cutover (branch
`anthonygwalters/feat/claude-branchingminds-sipps-cutover`) after the BrM sensor
is started and `stg_branchingminds__intervention_plans` has materialized in
prod. dbt Cloud CI also needs that staging model built into
`zz_stg_kipptaf_branchingminds`, since CI defers unmodified models to the
staging copies.

Rules the review added to the rollup:

- A plan whose end precedes its start cannot pull the running end below a plan
  that shares its start date: the running max uses `greatest(start, end)`, and
  the window orders tiebreak on plan id.
- Rows stop at the current school year. A plan whose planned end falls in a
  later year gets that year's row once the year starts.
- A plan whose `student_number` is null is dropped rather than merged with other
  unmatched plans.
- Episode attributes come from the plan with the latest real start date, not the
  latest clamped July 1 start.
- The grain test is `unique` on the surrogate key alone; the
  `unique_combination_of_columns` over the same 4 inputs was redundant.
- Unit-test fixtures that depend on the current school year derive their dates
  from today, so no test breaks on July 1.
