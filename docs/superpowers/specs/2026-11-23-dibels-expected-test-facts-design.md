# DIBELS expected-test facts for Cube: design

Spec issue: [#6473](https://github.com/TEAMSchools/teamster/issues/6473). Hub:
[#6461](https://github.com/TEAMSchools/teamster/issues/6461), which holds the
field inventory and the decisions on it.

## Why

The Literacy Dashboard is the only place staff see DIBELS participation,
progress monitoring (PM) and aimline results. Cube holds DIBELS Benchmark scores
for tested students only. It has no row for a student who was expected to test
and did not, no PM rounds, no aimline data and no goals.

Cube needs those rows so the dashboard's participation, PM and aimline pieces
can be built in Cube (PR PM4 on the hub) and checked against the dashboard.
Because the dashboard is the only reporting surface anyone sees today, Cube has
to match it 1:1.

## Goals

- 3 facts, 1 per chain: Benchmark expected tests, aimline PM, internal PM. Each
  holds 1 row per student, expected round and expected measure, whether or not
  the student tested.
- The facts hold the same students as the dashboard.
- `rpt_tableau__dibels_dashboard` is not edited.
- A drift test per chain compares the new intermediate with the dashboard model,
  so a change to either side that makes them disagree is caught.
- Goal dimensions for the benchmark goal counts and the internal PM goals.
- Build order: Benchmark, then aimline, then internal PM.

## Non-goals

- Pointing `rpt_tableau__dibels_dashboard` at the new models. That is the
  follow-up that ends the parallel build.
- Cube cubes, views and measures. That is PR PM4.
- Sight words (PR SW1 and SW2 on the hub).
- Fixing the dashboard's known issues. Each one carries over as it is, apart
  from the cases under _Where the facts cannot match the dashboard_.
- `aimline_season_student_goal` and its gap: academics asked that they not be
  shown (2026-09-24). The Trajectory columns: they are being dropped.

## Anti-goals

- A fact or intermediate shared by both PM methods behind a `model_type` column.
  Every consumer that forgets the filter counts each student twice, and no test
  fails.
- Any change to a number on the live dashboard as a side effect of this work.
- A mart that reads `int_extracts__student_enrollments_subjects`, directly or
  through another model (rule A12).
- The verdict rules written a second time. The facts read the verdicts from
  `int_amplify__pm_met_criteria` and `int_amplify__pm_met_criteria_aimline`.
- Duplicate rows copied from the dashboard model into a fact.

## Decided

Anthony Walters decided each of these on 2026-11-23.

| Decision                 | Choice                                                                                                                  |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| Facts                    | 1 per chain, no shared PM fact                                                                                          |
| Benchmark scores         | The Benchmark fact stores its own score, level and composite. Average-score measures stay on the existing view          |
| Internal PM              | Gets its own fact this year. Both methods run in parallel                                                               |
| Order                    | Benchmark, aimline, internal PM                                                                                         |
| Who is in the facts      | The dashboard's students: `enroll_status in (0, 2, 3)`, `is_self_contained is not true`, `not is_out_of_district`       |
| How it is built          | Approach B below, with drift tests against the dashboard model                                                          |
| Benchmark score pick     | Match the score as the dashboard does, with no grade. When a student has 2 sittings, the one at the enrolled grade wins |
| If the roster PR is late | Benchmark moves to the Dec 4 checkpoint with it. The roster PR stays its own PR                                         |

## Approaches

Two were ruled out early. A fact cannot read an `rpt_` model (A1). The verdict
rules cannot move into Cube YAML: they are about 700 lines of Teaching and
Learning's rules across the 2 criteria models.

- **A. One shared build.** Move the expected-test logic out of
  `rpt_tableau__dibels_dashboard` into 3 intermediates. The facts read them and
  the dashboard model is rewired to read them. Cube and the dashboard match by
  construction. It rewrites a 991-line model behind the only reporting surface
  in use, in the week of the deadline.
- **B. Parallel build, converge later (picked).** 3 new intermediates feed the
  facts only. The dashboard model stays as it is. The match is proven by a
  reconcile and kept by drift tests, and 2 copies of the logic exist until the
  follow-up.

Anthony picked B on the condition that the intermediates are tested against the
dashboard model. The dashboard is what people use, so protecting it matters more
this month than removing the duplication.

B goes against one repo rule on purpose. `.claude/rules/dbt-yaml.md` says 2
models that must cover the same students should read 1 shared upstream model,
and warns that a test comparing 2 separately built models also catches the gap
between their rebuild times. The drift tests are temporary. They retire when the
dashboard model reads the facts.

## What exists today

`rpt_tableau__dibels_dashboard` is 3 `union all` branches. Each one:

1. crosses the enrollment spine (`int_extracts__student_enrollments_subjects`,
   Reading rows) with an expectation gate on year, region and grade, keeping
   stints that overlap the round's window;
2. picks 1 stint per student, round and measure (`stint_candidates`,
   `stint_anchors`, `picked_stints`): the latest stint that holds the test date,
   or the window's last day when untested, else the latest overlapping stint;
3. left joins the score from `int_amplify__all_assessments`, the round status
   from `int_students__dibels_participation_roster`, the verdicts from the
   chain's criteria model, and the student's primary ELA section.

| Branch   | Gate                                                        | Extra inner joins                                                                                          |
| -------- | ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| BM       | `int_google_sheets__dibels_expected_assessments`            | none                                                                                                       |
| Internal | `int_google_sheets__dibels_pm_expectations`                 | `stg_google_sheets__dibels_pm_goals`; the composite row with `overall_probe_eligible = 'Yes'`              |
| Aimline  | `int_google_sheets__dibels__expected_assessments_by_levels` | `int_amplify__benchmark_student_summary` with `rn_pm_eligibility = 1`, matched on the student's own cohort |

Read `.claude/skills/dibels-dashboard/references/model-architecture.md` and
`docs/models/dibels-dashboard-data-model.md` before changing anything here. They
record which odd-looking rules are deliberate.

### Why the facts cannot read what exists

- The dashboard model is an `rpt_`.
- The roster reads the extract spine for enrollment and for 4 columns
  (`boy_probe_eligible`, `moy_probe_eligible`, `dibels_boy_composite`,
  `dibels_moy_composite`). Both criteria models read the roster. So a fact that
  carries a verdict or a round status reaches the extract spine through them,
  which A12 forbids. The roster is the only such route: no other model in the
  chain reaches an `int_extracts__` model.
- `int_amplify__*` and `int_google_sheets__dibels*` are source intermediates. A
  mart reads them only through a domain intermediate (A1).

### Measured on prod, 2026-11-23

- `rpt_tableau__dibels_dashboard`, academic year 2026: BM 139,370 rows, Internal
  45,121, Aimline 39,213. All 4 regions on each. 5 PM rounds opened. These
  counts include the dashboard's repeated rows.
- Enrollment: `int_students__student_enrollments` carries every column the spine
  joins and filters on. Compared with the extract spine for K-8 across academic
  years 2024 to 2026, about 27,900 stints match on year, student and entry date.
  Fewer than 10 a year differ on exit date or `enroll_status`, and fewer than 10
  stints in 2026 are in the domain model only.
- Those differences are refresh timing, not logic. The extract spine is built
  from `int_students__student_enrollments` through left joins only
  (`base_powerschool__student_enrollments` is a `select *` of it). The spine is
  a table rebuilt at 01:00; the domain model is a view. The comparison ran in
  the afternoon, about 12 hours after the spine's rebuild.

### Refresh times that matter

| Model                                        | Kind and schedule                |
| -------------------------------------------- | -------------------------------- |
| `int_extracts__student_enrollments_subjects` | table, rebuilt `0 1 * * *`       |
| `int_students__student_enrollments`          | view                             |
| `int_students__dibels_participation_roster`  | view                             |
| `rpt_tableau__dibels_dashboard`              | view                             |
| Literacy Dashboard extract                   | refreshed `0 5 * * *`            |
| The other assessment marts                   | tables, `30 0,10,13,15,17 * * *` |

## The build

### Step 0: move the roster off the extract spine (its own PR)

`int_students__dibels_participation_roster` reads enrollment from
`int_students__student_enrollments` and the 4 eligibility columns from
`int_amplify__benchmark_student_summary`, with the same row pick the extract
uses today. Its filters stay: ELA, `enroll_status in (0, 2, 3)`,
`grade_level <= 8`. It stays a view.

This is the one edit to a model the live dashboard reads. It is not additive, so
it ships alone, ahead of the facts. Its proof is a row-for-row comparison of the
dev build with prod on the roster's grain, with every differing row traced to a
cause before merge.

It leaves one known risk. Today the dashboard's own rows and the roster both
read enrollment as of the 01:00 spine. After Step 0 the roster reads enrollment
live. A stint added, closed or re-dated between 01:00 and the 05:00 dashboard
refresh can leave that student's rows without a round status until the next
night. Few enrollment changes happen in those 4 hours, so this should be rare.
The Step 0 proof measures it, and Anthony decides at review whether it is
acceptable.

Two fixes were considered and dropped. A nightly table copy of the enrollment
model would be a second model at the same grain (A4). Making the roster a table
on the spine's tick would freeze its scores at 01:00 while the dashboard reads
scores live at 05:00, which is a larger mismatch.

### Intermediates

3 new domain intermediates in `models/assessments/intermediate/`, 1 per chain.
Working names:

- `int_assessments__dibels_benchmark_expected_tests`
- `int_assessments__dibels_aimline_expected_tests`
- `int_assessments__dibels_internal_expected_tests`

Each rebuilds its branch of the dashboard model on
`int_students__student_enrollments`, with the same gate, the same extra inner
joins, the same stint pick and the same left joins. Each keeps the dashboard's
filters on students. Each has a uniqueness test at `error` on its grain:
student, academic year, expected test, expected round and expected measure
standard.

The Reading filter on the extract spine has no equivalent to copy: it only
selects 1 of the spine's 2 subject rows per stint.

The Benchmark score join needs 1 change from the dashboard's.
`int_amplify__all_assessments` is unique only with `assessment_grade_int` in its
key, and the dashboard's Benchmark join has no grade, so a student who sat at 2
grades gets 2 rows there. The intermediate matches the score as the dashboard
does and, when 2 sittings match, keeps the one whose `assessment_grade_int`
equals the stint's grade. A student who sat only at another grade keeps that
score and reads Tested, as on the dashboard. This is a row pick below the
staging layer, so the model declares `standard_exempt` for A5 with that reason.
The PM score joins have no grade either: check each for the same collision and
apply the same rule where one exists.

The ELA section join returns at most 1 section per row, because
`rn_core_subject_year` is numbered within source project, year, school, student
and core subject. The section follows the picked stint's school, as on the
dashboard, so a student who changes school mid-year can carry different teachers
on different rounds.

Columns that describe the student, school or section do not go in these models.
The facts reach them through keys.

### Drift tests

1 singular test per chain in `src/dbt/kipptaf/tests/`, comparing the
intermediate with the matching `model_type` rows of
`rpt_tableau__dibels_dashboard`. It returns 1 row per violation:

- a key the dashboard holds and the intermediate does not;
- a key the intermediate holds and the dashboard does not;
- a key both hold where a compared column differs.

Compare on the grain above, against the dashboard's distinct rows, since the
dashboard repeats some keys. Compare every column the two share that the fact
will carry: scores, levels, goals, statuses, categories and round fields. Leave
out `expected_round_selection`, which reads today's date and so differs between
a table built earlier and a view read now. On a key where the dashboard holds 2
sittings, compare against the sitting the pick rule keeps.

Each intermediate is a table, with the test's `meta.dagster.ref` naming it. A
test runs only when its host model materializes, and a view rebuilds only when
its code changes, so a view host would check for drift at deploy time only. dbt
Cloud CI also runs the test when either side changes, because the test is a
child of both.

Severity: each test lands at `warn` and moves to `error` once its query returns
0 rows in prod. If enrollment timing keeps a few rows above 0 (see
_Materialization and schedule_), scope the test to students whose stints agree
between the 2 enrollment models, so the logic comparison stays strict.

### Facts

3 facts in `models/marts/facts/`, each a thin select over its intermediate.
Working names:

- `fct_dibels_benchmark_expected_tests`
- `fct_dibels_aimline_progress_monitoring`
- `fct_dibels_internal_progress_monitoring`

Each fact:

- has a surrogate primary key over its grain;
- carries `student_enrollment_key` for the picked stint, hashed through the
  `student_enrollment_key` macro, which reaches school, grade and region;
- carries a nullable key to the student's primary ELA section enrollment, for
  teacher, course and section. A null key is the dashboard's `scheduled = 0`;
- carries the expected window's start and end and the test date as `_date_key`
  columns;
- keeps the `expected_*` columns filled on every row, and the score-side columns
  null when nothing was sat;
- carries the fields the hub inventory marks "PM fact (Anthony)" that belong to
  its chain, renamed to the mart rubric (R1 to R10);
- tags every student-level column `config.meta.contains_pii: true`;
- is listed in `cube.yml` under `cube_semantic_layer.depends_on`.

The Benchmark fact carries its own score, level, percentile, growth and
composite columns. The aimline fact carries `goal` (the student's own aimline
value on the probe date), the cohort, the aimline categories and
`missed_aimline_consecutive`. The internal fact carries the score, the verdicts
and `benchmark_goal_gap`, which vary by student. Its goal values do not vary by
student, so it carries a key to the internal PM goals dimension instead of
copies of them (R9).

### Goal dimensions

The hub proposed 1 goals dimension. The goal sheets hold values at 3 grains, and
a dimension holds 1 value per row at its own grain, so this design has 3:

- Benchmark school goals, from `stg_google_sheets__dibels_bm_goals`: 1 row per
  year, school, grade and season, holding the admin goal and the school counts.
  The Benchmark fact carries a nullable key to it, null until the BM Goals paste
  lands.
- Benchmark region goals, from the same sheet: 1 row per year, region, grade and
  season, holding the region counts. The sheet repeats them on every school row,
  and a test already asserts they agree across a region's schools. On school
  rows, a sum across schools would count them once per school.
- Internal PM goals, from `stg_google_sheets__dibels_pm_goals`: 1 row per year,
  region, season, grade, measure standard and round. The internal fact keys to
  it. The workbook also reads this sheet directly for 6 fields, so Cube needs it
  at its own grain.

Each needs a domain intermediate over its staging model, because a mart does not
read `stg_` directly.

### Materialization and schedule

The intermediates and the facts are tables on 1 nightly cron tick of their own,
between the extract spine's 01:00 rebuild and the dashboard's 05:00 refresh, as
late as the build's run time allows. The dashboard changes once a day, so a
build just before its refresh gives Cube the same enrollment and nearly the same
scores as the dashboard shows that day. It also keeps the drift tests quiet: on
the other assessment marts' tick, which runs through the day, each test would
report every stint that changed since 01:00.

As table marts the facts carry no `foreign_key` constraints: each edge goes
under `config.meta.foreign_key`.

### PR sequence

| PR  | Holds                                                                         |
| --- | ----------------------------------------------------------------------------- |
| PM0 | Step 0: the roster off the extract spine                                      |
| PM1 | Benchmark intermediate, its drift test, the 2 benchmark goal dimensions, fact |
| PM2 | Aimline intermediate, its drift test, fact                                    |
| PM3 | Internal intermediate, its drift test, the internal PM goals dimension, fact  |

Each PR is based on `origin/main`, carries `Refs #6473` and `Refs #6461`, and is
not linked to either issue, so a merge closes neither.

PM1 cannot pass `dbt-layer-check` until PM0 is on `main`: the check follows
lineage, and the Benchmark intermediate reads the roster. Start PM0 first and
build PM1 on its own branch in parallel. If PM0 merges late, Benchmark moves to
the Dec 4 checkpoint with it. Do not stack PM1 on PM0's branch: a stacked base
skips `claude-review` and dbt Cloud CI.

### Proof for each PR

- `uv run dbt build --select <model>+ --project-dir src/dbt/kipptaf --target dev`
  passes, uniqueness tests included.
- The drift test's query against the dev build returns only rows with a named
  cause.
- Row counts by region reconcile to the dashboard's distinct keys.
- Every key column is populated: no mart test fails on a key that is null on
  every row.
- `dbt-layer-check` reports no new A1 or A12 edge.
- `docs/models/dibels-dashboard-data-model.md` and the `dibels-dashboard` skill
  are updated for the new models, as that skill requires before any push.

## Where the facts cannot match the dashboard

- **Repeated rows.** The dashboard model repeats a row when 2 enrollment stints
  overlap, and when a student sat a Benchmark measure at 2 grades. A fact has a
  unique key, so distinct-student counts match and raw row counts do not on
  those keys.
- **Enrollment timing.** A stint that changed between the extract spine's
  rebuild and the facts' build.

## Left to the builder

- Final model and column names, and which inventory field lands on which fact.
- Whether the 3 intermediates share the stint pick through a macro or repeat it.
  A shared model with a `model_type` column is not an option.
- The row pick for the roster's 4 eligibility columns, copied from the extract.
- Whether the fact also carries `student_key`, given that the enrollment key
  already reaches the student (strict-chain rule).
- Whether the 2 routes to the enrollment, direct and through the ELA section
  enrollment, count as a diamond path, and what to do if so. The same question
  applies to how the benchmark school goals dimension names its school, as text
  or as a location key. Settle both with the data-engineer reviewer.
- Whether `benchmark_goal` on the aimline fact, which comes from the by-levels
  gate and does not vary by student, stays a value or moves to a dimension.
- The exact minute of the nightly tick, and the exact list of compared columns
  in each drift test.

## Open with the owner

- Anthony reviews each difference the roster comparison and the drift tests
  surface, and decides whether it is acceptable. That includes the Step 0 risk
  above.
- Filing the follow-up issue that points the dashboard model at the facts and
  retires the drift tests. Ask before filing.

## Constraints

- Benchmark is single-sourced from the internal gate and is never by levels.
- Consumers filter `assessment_include is null`. Never filter it inside a gate.
- `rn_pm_eligibility = 1`, with `assessment_grade_int` in its partition, gives 1
  row per benchmark sitting. Do not drop the grade.
- `overall_aimline_composite_level` uses the literal `'No data'`, never null.
- A PM round is measured against the next benchmark's standard.
- Slice on the `expected_*` columns. A score-side filter drops untested
  students.
- `region` is the city form (`Newark`, `Camden`, `Miami`, `Paterson`).
- Nothing in a commit, PR or issue names a student or shows a row. Counts under
  10 read `<10`.
- Dates: Benchmark targets Nov 30. PM and aimline fall back to the Dec 4
  checkpoint on the hub.

## Revision 2026-11-23: Step 0 is deferred, and the intermediates read the spine

Step 0 was built and compared with prod, then held. Its logic is equivalent to
the old read. Its timing has 3 effects on the live dashboard:

- A student whose stint changed after the spine's 01:00 rebuild loses their
  round status on the dashboard, and their PM round verdict with it, because
  both criteria models inner join the roster.
- PowerSchool's full nightly refresh runs at 02:00, between the spine's rebuild
  and the dashboard's 05:00 refresh, so that happens every night.
- The roster then inlines the enrollment view, and the dashboard model expands
  the roster 5 times. One read of the dashboard model bills about 2.4 times as
  much, and a query that references the dashboard model twice no longer plans.

The Step 0 code is parked on branch
`anthonygwalters/refactor/claude-dibels-roster-off-spine`, with no PR. Whether
to ship it, to exempt the facts from A12 with `config.meta.standard_exempt`, to
rework it onto `int_students__student_enrollment_union`, or to move the spine's
or the PowerSchool refresh's schedule is deferred to an issue for the
data-engineer reviewer, linked from #6473.

Until that issue is decided, this design changes as follows.

- PM0 leaves the sequence. PM1 to PM3 do not wait on it.
- The 3 intermediates, their drift tests and the goal dimensions are built and
  merged. A12 applies to marts only, so an intermediate may read the roster and
  the criteria models as they are.
- The 3 facts are built in dev, so PR PM4 can be written against them. They
  merge once the issue is decided.
- The intermediates read enrollment from
  `int_extracts__student_enrollments_subjects`, as the dashboard model does, not
  from `int_students__student_enrollments`. The roster reads the spine, so an
  intermediate that read enrollment live would disagree with the roster for a
  student whose stint changed after the spine's rebuild, and would carry a blank
  round status. Keep the enrollment read in 1 CTE in each intermediate, so it is
  a 1-line change if Step 0 ships.
- With enrollment from the spine, the intermediates see the dashboard's own
  enrollment. The _Enrollment timing_ entry under _Where the facts cannot match
  the dashboard_ does not apply, and a drift test has no timing rows to scope
  out.
- Each drift test references the dashboard model once and its intermediate, a
  table, once. Do not write one that references the dashboard model twice.
- The nightly tick only has to follow the spine's 01:00 rebuild. Keep it as late
  before 05:00 as the build's run time allows, so scores match what the
  dashboard shows that day.
