# Model architecture

How the internal and aimline chains are built and kept apart, and the join and
grain hazards that have bitten.

## Growth fields on `int_amplify__all_assessments`

T&L asked for "% of students that made above average growth" BOY-to-MOY and
MOY-to-EOY. Two rounds of verification were needed before building anything --
don't skip either check on a similar ask elsewhere in this dashboard.

**Round 1 -- does growth data exist and reach this model at all?** Yes.
`measure_semester_growth` / `measure_year_growth` (both `string`) survive the
full lineage: `stg_amplify__mclass__{sftp,api}__benchmark_student_summary` ->
union -> unpivot -> `int_amplify__all_assessments`. Confirmed grain against live
prod data:

- **BOY** row: both null (no prior period to grow from)
- **MOY** row's `measure_semester_growth` = BOY-to-MOY growth
- **EOY** row's `measure_semester_growth` = MOY-to-EOY growth
- **EOY** row's `measure_year_growth` = BOY-to-EOY (full year) -- a THIRD
  comparison nobody asked for here. Don't conflate it with MOY-to-EOY.

Values are Amplify's 5-level categorical classification (`Well Below Average` /
`Below Average` / `Average` / `Above Average` / `Well Above Average`), `'NA'` on
PM rows (this concept is Benchmark-only). Sanity-checked against a real student
(107119, Newark, AY2025): raw score climbs every period (expected -- the test
scales with grade difficulty), but the **percentile** column is what growth
actually tracks -- percentile flat/up between two periods reads `Average`+,
percentile down reads `Below Average`-. Growth tracks relative national
standing, not raw score.

**Round 2 -- "% of students above average growth" is NOT the categorical field
above.** T&L's actual ask is "above the average", i.e. compute a mean growth
number across some population and flag students who beat it -- a population
statistic, not Amplify's pre-baked norm-referenced bucket. That statistic does
not exist anywhere in the source. Building it needs:

- **A base metric**: `measure_percentile` delta between periods, or
  `measure_standard_score` delta. `measure_percentile` (float64, a point-in-time
  national-norm standing) DOES flow through to `int_amplify__all_assessments`,
  but it's a status snapshot, not a growth number -- there is no raw growth
  percentile / SGP field anywhere in the amplify source models, confirmed by
  grepping for `growth.*percentile|percentile.*growth` across the whole package
  (zero hits).
- **A reference population**: average over grade+region? grade+school?
  network-wide per grade? T&L's call, not something to guess -- put it to them
  as an explicit multiple-choice question if it comes up, don't build against an
  assumed default.

**Shipped so far**: `is_above_average_growth` (boolean) on
`int_amplify__all_assessments`, derived from the categorical field only --
`true` when `measure_semester_growth` is `Above Average` or
`Well Above Average`, `false` for
`Average`/`Below Average`/`Well Below Average`, `null` on `BOY` rows and on `PM`
rows (`measure_semester_growth` is always `'NA'` there, so the concept doesn't
apply). This satisfies "flag against Amplify's own average" -- it does NOT
satisfy "average across our own population", which is the unresolved Round 2
question above.

**BigQuery gotcha hit while adding it**: a bare `null` in one `UNION ALL` branch
and a real `BOOL` expression in a sibling branch fails with
`Column N in UNION ALL has incompatible types: BOOL, INT64` -- BigQuery infers a
bare `null` as `INT64` by default. Fix:
`cast(null as bool) as is_above_average_growth` in the branch that doesn't
compute it.

## Benchmark is not per data model -- it must be single-sourced

`data_model` distinguishes the two **PM** methods. Benchmark has no such split:
it tests every student against one set of expectations, so its rows carry
`data_model = 'Benchmark'` and are emitted from **one** branch only.

**Benchmark will never be by levels.** That is a standing rule from academics,
not a description of today's data -- Benchmark has no Below / Well Below cohort
because it is what assigns students to those cohorts in the first place. So the
by-levels range holds PM rows only, and Benchmark belongs in the 16-column
source. Do not add Benchmark rows to the by-levels tab, and do not "restore"
them if a future paste drops them.

The `if(assessment_type = 'Benchmark', 'Benchmark', <branch>)` sits on BOTH
branches even though the aimline side can no longer fire it. That is the
invariant expressed as code: if Benchmark ever does reappear in by-levels, the
two rows collide on the grain and the uniqueness test fails, rather than
silently doubling. Filtering Benchmark out of the aimline branch instead would
drop it quietly, which is worse.

Getting this wrong is silent. When the stack first landed, Benchmark rows were
emitted from both branches at identical counts (576 and 576 for AY2026), and
three things broke without any test or contract failing:

- `rpt_tableau__dibels_dashboard`'s Benchmark branch inner-joins the gate on
  `assessment_type = 'Benchmark'` with **no `data_model` predicate**, so every
  Benchmark row doubled.
- `int_students__dibels_participation_roster` computes
  `count(*) over (partition by academic_year, region, grade, admin_season, round_number)`
  as `expected_row_count`, counting both branches. Measured: prod runs 4-8
  expected rows per group, the stacked version 8-16. That halves every
  benchmark-completion percentage.
- The grain test on the intermediate still passed, because `data_model` is part
  of its key. A duplicate across branches is a legitimate row by that
  definition.

**The two branches' Benchmark rows are not interchangeable.** They agree on
dates, criteria, rounds, credit type and subjects, and differ on exactly one
column: `month_round`, on ~96 rows a year. The by-levels range carries the
corrected values and V1 carries the stale network-wide labels, because the
`month_round` fix was only ever run against the new tab. Miami AY2026 is the
clearest case -- BOY starts 2026-09-08, and V1 says `August` while by-levels
says `September`; EOY starts 2027-04-26, V1 says `May`, by-levels says `April`.

So either source Benchmark from the by-levels branch, or fix V1's `month_round`
first. Fixing V1 is preferable -- then the branches agree and the constraint
disappears -- but note that neither one-shot fix would have targeted it: the
Benchmark `month_round` fix indexed a 17-column layout, the derived-column
backfill indexed 18, and V1 is 16. The rule is small enough to re-derive:
`month_round` is the month of that Benchmark round's `Start Date` in
`reporting__terms`, keyed on `(academic_year, region, admin_season)`.

## The participation roster spans three expectation models

`int_students__dibels_participation_roster` answers "was this student expected
to test, and did they" -- and that question now has three different shapes. Its
`expected_row_count` partition has to match the model, or students get penalised
for rounds they were never in.

| Model       | Expected-count grain                                                                                                                             |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Benchmark   | region / grade / season. Steady year over year.                                                                                                  |
| Internal PM | region / grade / season / round. Below and Well Below are tracked **together** -- they are expected to test the same measures in the same round. |
| Aimline PM  | region / grade / season / round / **`measure_standard_level`** / measure standard.                                                               |

The aimline row is the one that changes behaviour, in principle: its expected
set is per cohort, so if a round tests Well Below only, a Below student was
never expected to test and counting them against a cohort-blind expected set
marks them non-participating for a round they were correctly absent from. The
cohort has to be in the partition **and** matched to the student's own level.

**In today's data it changes nothing, and you should say so rather than quote a
figure.** Measured on the live by-levels sheet: 790 AY2025
`(region, grade, season, round, measure)` combinations, every one present for
both cohorts -- zero cohort-only rows in either direction. The sheet was built
by duplicating the 16-column PM rows per cohort, so it is symmetric by
construction. Build the cohort into the grain anyway, so a future split needs no
restructuring, but do not claim an asymmetry exists. If a prior version of this
skill or a model description cites a Well-Below-only row count, it was not
measured -- re-derive it before repeating it.

Worth raising with academics: the by-levels sheet as it stands does not express
the differentiated testing the aimline model was built to support.

## The two chains share no model -- split at the source, not behind a flag

| Chain                | Range                          | Gate                                                        | PM expectations                             |
| -------------------- | ------------------------------ | ----------------------------------------------------------- | ------------------------------------------- |
| Internal + Benchmark | 16-column Expected Assessments | `int_google_sheets__dibels_expected_assessments`            | `int_google_sheets__dibels_pm_expectations` |
| Aimline              | 18-column by-levels            | `int_google_sheets__dibels__expected_assessments_by_levels` | none — the gate is the whole chain          |

**Do not reach for a discriminator here.** It was tried: one gate unioning both
ranges, tagged `data_model` (`internal` / `aimline` / `Benchmark`), in the grain
and in the `min_pm_round` / `max_pm_round` partition. It was abandoned, and the
reasons generalize:

- The flag carried the exact hazard it was supposed to manage. Every consumer
  inner-joins the gate as a membership test, so one that forgot to filter
  `data_model` matched every score twice. Measured on
  `rpt_gsheets__dibels_pm_goal_setting`: 1,650 rows against a real grain of 550.
- It changed the internal gate's column set for no benefit to the internal
  chain, which is the one with a prod contract and live consumers.
- Benchmark had to be assigned to a branch anyway, and emitting it from both
  doubled every dashboard Benchmark row and inflated participation expected
  counts from 4-8 to 8-16. CI caught none of it.

Splitting at the source removes the column and the hazard together, leaves the
internal gate byte-identical to what its consumers expected, and made
`rpt_gsheets__dibels_pm_goal_setting` a no-change model. The user's framing was
_"i legit think we should just split things between internal and aimline"_ --
and that applies to the gate, not only to the PM expectations below it.

The aimline gate differs from the internal one in two ways beyond the source:
`measure_standard_level` is in the grain **and** in the min/max round partition
(a shared partition would give both cohorts the wider range once a round is
expected of only one), and its terms unnest is a `cross join` rather than a
`left join`, because every row in that source is a PM round and every PM terms
row carries a band -- there is no null-band Benchmark row to preserve.

The model also opens with a `terms` CTE that explodes `reporting__terms` on
`grade_band` into one row per grade level, so a grade joins its own band's
window. A Benchmark row has no band, so its `grade_level` is null and the join
lets any grade match -- the grade is inherited from the expected-assessments
side. Before this, the join had no grade predicate at all, which fanned AY2025
PM out 3x (2,370 rows against 790 real ones) and let a grade pick up a band's
dates that did not include it.

## Do not hoist a downstream filter into the shared gate

Tempting and wrong: `assessment_include is null` is repeated at four consumers
(`int_students__dibels_participation_roster`, three sites in
`int_amplify__all_assessments`, `rpt_tableau__dibels_dashboard`), so putting it
once in `int_google_sheets__dibels_expected_assessments` looks like a cleanup.
Two things break.

1. **`min_pm_round` / `max_pm_round` change silently.** `WHERE` is evaluated
   before window functions, so filtering in the same `SELECT` that computes them
   makes the season's first and last round exclude cancelled rounds. Measured on
   AY2025: 675 rows shifted on `min_pm_round`, 1,386 on `max_pm_round`. Whether
   a cancelled round should still bound the season is a real question for
   academics -- it is not a question to answer as a side effect of deduplicating
   a filter.
2. **`pm_expectations` stops matching prod.** It does not project
   `assessment_include`, so its consumers cannot filter and prod's dashboard PM
   branch has always included cancelled rounds. Dropping them upstream changes
   PM participation counts network-wide.

The gate's own properties yml already documents the contract -- _"Rows are
switched off with `assessment_include` rather than filtered in SQL... downstream
models express that as `assessment_include is null`"_ -- so a filter in the gate
SQL contradicts the model's own description. Leave it to consumers. The aimline
model is a consumer and applies it itself.

## The Benchmark half moved to `int_amplify__benchmark_student_summary`

`int_amplify__all_assessments` used to compute benchmark composites, the
aggregated level columns and `overall_probe_eligible` inline, then reuse them in
its PM branch. With two PM methods, both needing the same eligibility, that had
to move upstream. The new model holds the whole Benchmark half;
`all_assessments` selects from it and adds four columns (`illuminate_subject`
plus typed nulls for `probe_number`, `total_number_of_probes`, `score_change`).

Three things about it are load-bearing:

- **`rn_pm_eligibility` is how the PM branches get one row per administration.**
  The model's own grain is one row per measure, so a PM round joined to it
  without this filter fans out by the measure count (measured 9x and 7.6x on the
  two methods before the fix). Both PM branches filter `rn_pm_eligibility = 1`.
- **`assessment_grade_int` is in that partition, and must stay.** A student can
  be assessed at two grades inside one benchmark window; each sitting is its own
  administration with its own expectations, and the PM consumers join assessed
  grade to enrolled grade. Leaving it out looks like tighter dedup and silently
  drops the second sitting. Per the user: "we can have mid benchmark grade level
  changes and there is nothing we can do about it."
- **`overall_aimline_composite_level` uses the literal `'No data'`, never
  null.** It inner-joins to `measure_standard_level` on the by-levels gate, and
  null joins to nothing -- which would look identical to "not eligible" but for
  the wrong reason. `'No data'` and `At/Above Benchmark` both match no by-levels
  row, which is correct: neither is aimline-eligible. Do not "simplify" it back
  to null.

The `order by` in `rn_pm_eligibility` prefers the Composite row but does not
require one. `row_number()` always assigns 1 within a partition, so a
student-period with no Composite row still yields exactly one row -- 312 such
student-periods in AY2025, all retained. If someone asks "does a student without
a composite get dropped?", the answer is no, and that is the reason.

## `region` on the aimline PM model must be the city form

`int_people__location_crosswalk` has two region-ish columns and they are not
interchangeable. `location_region` is the long-form legal entity name
(`TEAM Academy Charter School`). Every DIBELS model joins on the city form --
`Newark`, `Camden`, `Miami`, `Paterson` -- derived as:

```sql
initcap(regexp_extract(lc.location_dagster_code_location, r'kipp(\w+)')) as region,
```

Emitting `location_region` from
`int_amplify__mclass__pm_student_summary_aimline` made the expectation-gate join
never match. At the time the PM branches LEFT joined the scores, so it surfaced
as 35,546 aimline rows in which every single row was untested, with no error
anywhere. The branches inner-join now, so the same mistake would instead produce
**zero aimline rows** -- louder, but still not an error. Either way, diagnose
this class of bug by adding the join predicates cumulatively and watching where
the row count collapses; a region join that resolves to the wrong name form
fails silently in both shapes.

## `UNION ALL` binds by position, and a same-typed misplacement is silent

Two bugs of this shape in one session on `int_amplify__all_assessments`:

- `score_change` (NUMERIC) at position 29 in one branch against `model_type`
  (STRING) in the other. **Failed loudly** -- types disagreed.
- `overall_probe_eligible` at position 32 in the PM branch against position 37
  in the Benchmark branch. Both STRING, so BigQuery accepted it. It surfaced
  only because `model_type` started returning `'Yes'` in query output.

So a clean build is not evidence the branches line up. When editing either
branch of a wide union, diff the two projected column lists by ordinal, not by
eye. The repo convention of enumerating columns per branch (never `select *`) is
the correctness fix here, not just the CV03 lint fix.

## `all_assessments` carries scored rows only -- do not LEFT join the scores

An intermediate version of both PM branches LEFT joined the score source so that
"expected but not tested" became a row. **That was reverted, deliberately. Do
not reintroduce it.** This model has only ever carried scored rows, and Not
Tested is the participation roster's job.

The roster already answers it without help: it reads the gate directly, counts
the measures expected for a (year, region, grade, season, round) as
`expected_row_count`, and compares that to `actual_row_count` from this model.
The dashboard's PM branch does the same at measure granularity -- it drives off
the gate's `expected_measure_standard` and LEFT joins this model, so an unscored
measure still gets a named row there. Two places already manufacture the
absence; a third only lets them disagree.

Two things the LEFT-join version taught, both still worth knowing:

- **Untested rows carried no measure identity.** `measure_standard`,
  `measure_name` and `measure_name_code` all come off the score, so on an
  untested row they were null and every such row for a round was byte-identical.
  20,074 AY2025 rows collapsed to about 9,600 distinguishable ones. If anyone
  proposes emitting absences from a model again, the expected value has to come
  with them.
- **A window partition key from a LEFT-joined side is nullable.** `max_score`
  originally partitioned on `surrogate_key` and `measure_standard`, both from
  the score side: every untested row for a round collapsed into one partition
  and `rn_highest = 1` kept 8 rows out of 20,081. Any model that turns absences
  into rows has this hazard -- check every `partition by` against which join
  produced each column.

`max_score` now partitions on
`academic_year, student_number, model_type, round_number, expected_measure_standard`
and orders by `measure_standard_score desc, client_date desc`. **`academic_year`
is load-bearing**: round numbers restart every year, so without it a student's
AY2026 round 1 competes with their AY2025 round 1 for the same measure and one
real score is dropped. `model_type` keeps the two methods from ranking against
each other.

## A dedup step belongs to exactly one grain

The highest-value lesson in this whole refactor. It sat in prod for years,
produced no error, and understated real student outcomes.

Prod's `assessments_scores` unioned all three branches -- mCLASS Benchmark, DDS
Benchmark, PM -- into one CTE. A single `max_score` ranked the whole union and
the final `SELECT` split it back apart by `assessment_type`. **One dedup step,
two different kinds of row.**

Its sort key was `measure_standard_level_int desc`, which is correct for
Benchmark (the column holds 1-4; keep the highest level for the slot). The PM
branch writes `null as measure_standard_level_int` -- PM has no level -- so on
every PM row the sort had nothing to sort by and the pick among a student's
probes was whatever BigQuery reached first. `partition by surrogate_key` had the
same defect: it means the benchmark summary's key on one side, the PM model's
key on the other.

**Nobody chose a null sort key for PM.** They chose one for Benchmark, and PM
was in the same CTE. That is the shape to watch for.

It deduped PM at all only by accident:
`int_amplify__mclass__pm_student_summary`'s surrogate key used to omit
`probe_number` and `device_date`, so it collided across a student's probes --
67,984 AY2025 rows against 33,917 distinct keys. **Fixed in #5305**: the key now
covers student, school year, PM period, measure, probe, device date and
assessment grade, and the model carries a severity-error natural-key test. The
diagnostic lesson still stands: `count(distinct surrogate_key) < count(*)` on a
model whose key you have not read is not proof of fan-out -- using it that way
mis-read 1,352 genuine multi-probe rounds as gate duplication during this
session.

Measured on AY2025, every effect in one direction:

| Effect                                             | Rows  |
| -------------------------------------------------- | ----- |
| Round-measure slots holding more than one probe    | 1,352 |
| Reported score lower than the student's best       | 634   |
| `met_measure_standard_goal` flipped not-met to met | 139   |
| `met_admin_benchmark_goal` flipped not-met to met  | 85    |

Average understatement 10.25 points. Every flip went not-met to met: students
were told they missed a goal they had hit, and it propagated through
`met_measure_name_code_goal` to the round-level met/not-met on the dashboard.

**Separately, prod's PM completion gate never fires.** Every PM row in the prod
participation roster is `completed_test_round = false` -- all 39,981 across
`BOY->MOY` and `MOY->EOY`, not one `true`; only Benchmark seasons have true
rows. So prod can never credit an `AND` round whatever the student scored, and
its only 1s come through the null (OR) branch, which skips the gate. The
refactored roster produces 15,078 true Internal PM rows, so the gate fires for
the first time and PM attainment rises against prod. Corrected, not regressed --
say so before anyone compares the two.

**The rule: if a CTE unions grains and then ranks, one side's sort key is
meaningless on the other and nothing fails.** Dedup before the union, or split
the model. Extracting the Benchmark half is what gave PM its own `max_score`,
which is what made a PM-meaningful sort key possible at all.

Corollary for reviewers: when you see `order by <col> desc` in a window over a
UNION, check that `<col>` is populated in every branch. A `null as <col>`
literal in any branch is the tell.

## Miami needs focus_student_number on the aimline PM model too -- FIXED

**This was the unexplained 961-row gap between the two PM methods on AY2025. It
was a bug, not a design difference, and it was total for Miami. Fixed by
applying the macro in `int_amplify__mclass__pm_student_summary_aimline`. The
table below is the before state, kept so the symptom stays recognisable if it
regresses.**

| Region   | Internal rows / students | Aimline rows / students |
| -------- | ------------------------ | ----------------------- |
| Camden   | 8,686 / 1,111            | 8,686 / 1,111           |
| Newark   | 23,502 / 2,983           | 23,502 / 2,983          |
| Paterson | 3,358 / 382              | 3,358 / 382             |
| Miami    | 961 / 420                | **0 / 0**               |

Three regions match exactly. Miami loses every row.

**Cause.** `int_amplify__mclass__pm_student_summary` resolves the student id
through the `focus_student_number` macro (`src/dbt/kipptaf/macros/utils.sql`),
which adds 8,400,000,000 to a kippmiami id for `academic_year <= 2025`.
`int_amplify__mclass__pm_student_summary_aimline` does not apply it, so it
passes Amplify's raw 6-digit id straight through. Measured on AY2025: Miami ids
are 10 digits and every one of the 5,503 internal rows starts `8400`, against 6
digits on the aimline side. `int_amplify__benchmark_student_summary` keys on the
network number, so every Miami PM row fails that join in the aimline branch.

The tell is that the two sources look identical until you compare id SETS. Both
carry 67,984 AY2025 rows, 7,861 students, 8 measures, and identical per-region
row counts -- Miami 5,503 rows / 978 students on both sides. A full outer join
on `student_primary_id` is what exposes it: 978 Miami students resolve as
"internal only" and the same 978 as "aimline only". Compare sets, not counts.

**The fix, and where it has to go.** `focus_student_number` is applied in the
`enriched` CTE, taking `c.student_primary_id`, `c.academic_year` and
`lc.location_dagster_code_location` -- the crosswalk column directly, not the
`_dbt_source_project` alias derived in the same SELECT, since BigQuery has no
lateral column aliases. It must NOT go in `combined` or earlier: the full outer
join matches the two SFTP files on their shared raw id, so offsetting before
that join breaks the merge. `c.* except (student_primary_id)` plus the re-add
keeps the column name.

After the fix all four regions match between methods (Miami 961 rows / 420
students on both), the aimline model still holds 67,984 AY2025 rows with 67,984
distinct surrogate keys, the full outer join still merges 1:1 (0 rows with no
base side, 2,986 base rows with no aimline goal as before), all 5,503 Miami rows
carry the offset, and Benchmark stays byte-identical to prod.

**The macro is year-scoped -- keep the call anyway.** It offsets `year <= 2025`,
so from AY2026 Miami's raw id already IS the network number and the two sides
align without help. AY2026 cannot confirm that yet -- it has zero tested PM rows
in either method, since no PM scores have landed. Re-check once SY26-27 scores
arrive rather than assuming, and do not remove the macro call on the grounds
that the current year does not need it -- it is what makes the historical years
join.

**Do not chase this through the gates or the eligibility rule.** Ruled out by
measurement, in this order: expectations are identical (both methods 55,591
expected measures on AY2025, same 24,594 roster rows); gate coverage at
`(region, grade, admin_season)` is identical, zero rows on either side of a full
outer join; the two eligibility predicates select the same 9,405 benchmark rows,
because `overall_probe_eligible = 'Yes'` and
`overall_aimline_composite_level in ('Below Benchmark', 'Well Below Benchmark')`
are the same condition and the gate's `measure_standard_level` carries exactly
those two values; and the score-side filter
`enrollment_grade = assessment_grade and assessment_grade is not null` passes
67,896 rows / 7,861 students in both sources. Swapping one variable at a time is
what isolated it -- the internal gate and internal eligibility joined to the
AIMLINE source reproduces the aimline numbers exactly (4,476 students, 35,546
slots), which proves the gate is innocent.

## Slice on `expected_*`, never on a scores-side column

The dashboard has two parallel dimension sets. `expected_*` comes from the
enrollment spine crossed with the expectation gate and is populated on EVERY PM
row; the scores-side columns come through the LEFT join and are null wherever no
probe happened. AY2025, 89,730 PM rows: every scores-side column is null on
exactly the same 18,766 (9,383 per method), every spine column on zero.

Binding a view to the wrong one deletes the untested students from the
denominator. Nothing errors, every percentage still sums to 100, and the rate
goes UP. The symptom is a Not Tested slice disappearing after a field swap.

Three pairs are easy to confuse -- close names, identical values wherever both
exist, only one survives a non-test:

| Safe                         | Drops untested      |
| ---------------------------- | ------------------- |
| `expected_test`              | `period`            |
| `expected_measure_name_code` | `measure_name_code` |
| `expected_grade_level_int`   | `assessment_grade`  |

Also safe: `expected_round_number`, `expected_measure_name`,
`expected_measure_standard`, `expected_month_round`, `expected_start_date` /
`expected_end_date`, `region`, `school`, `student_number`, `grade_level_int`,
`round_test_status`, `measure_test_status`. Also unsafe: `measure_name`,
`measure_standard`, `measure_standard_level`, `client_date`, `start_date`,
`mclass_student_number`.

This is the owner's deliberate design -- the spine exists to force the nulls to
show -- so a view reaching for a scores-side dimension is a mistake to correct,
not a style choice.

## A code's standards are sat together, and a warn test guards the rollup

**Do not add an `Incomplete Measure` status.** It was proposed 2026-09-19 and
measured away: within a multi-standard code a student sits every standard or
none, because the pair comes off ONE probe administration (NWF-CLS and NWF-WRC
from a single NWF sitting, ORF and ORF-Accu from one passage). AY2025 partial
groups: 0 on Internal, 0 on Aimline. A dead enum value costs the next reader
more than it saves.

Aimline's partials are a publication gap, not a participation gap -- 1,030
groups where the student sat both and Amplify published one aimline, 868 where
it published neither. `No Aimline Data` already names that. `n_sat` is never 1.

`met_measure_name_code_goal` DEPENDS on the pairing: it rolls up with `avg()`
over the code partition and sees only verdicted rows, so a half-sat group would
report the sat standard's verdict as the whole measure's. Guarded by
`rpt_tableau__dibels_dashboard__measure_code_sat_all_or_none` at
`severity: warn`.

**If someone asks about that warning**, the diagnosis query, the corrected
rollup SQL, and why the fix reuses the aimline sibling's countif/min pattern
rather than a third shape are in the reference document under "If the
measure-code pairing test fires". Do not re-derive it -- and note that the fix
is the point at which `Incomplete Measure` stops being dead and becomes the
right value to add.

## Filtering PM rows: `assessment_type` and `model_type` say the same thing

On `rpt_tableau__dibels_dashboard`, `assessment_type = 'PM'` is exactly
`model_type in ('Internal', 'Aimline')` -- AY2025 gives PM/Aimline 44,865,
PM/Internal 44,865, Benchmark/BM 111,892, with no row crossing. Neither filter
narrows the other, so adding both proves nothing. Use `model_type`: it is the
column that separates the two PM methods, which is the filter a view actually
needs.

## The OR criteria is spelled NULL, and it is live on history

**Do not read the `else max()` branch as dead legacy.** `pm_goal_criteria` never
holds the string `'OR'` in any year. The OR behaviour is what **null** means,
and the `case pm_goal_criteria when 'AND' then min() else max() end` sends null
down the `max()` path.

The history, from `stg_google_sheets__dibels_expected_assessments` PM rows:

| Year | `AND`   | null  | Live rows                                          |
| ---- | ------- | ----- | -------------------------------------------------- |
| 2024 | 20      | 142   | **0** -- all switched off via `assessment_include` |
| 2025 | 254     | 536   | 222 AND, 367 null                                  |
| 2026 | **883** | **0** | 883 -- first fully-AND year                        |

So on AY2025 the OR path is live on 367 rows, more than half. SY26-27 is a clean
cut: every row is `AND`, no nulls at all.

**What the OR meant.** Academics used to let a student pass a round by meeting
one _set_ of measures or a single measure, rather than all of them. The code
expresses that exactly: `max()` runs over `met_measure_name_code_goal`, which is
already the AND-within-a-code (both NWF standards, both ORF standards). So a set
had to be complete, but only one set had to pass. From SY26-27 a student must
meet every measure, which is why every row is now `AND`.

**Consequences for `met_pm_round_overall_criteria`.** Its `case` has an `'AND'`
branch and a null branch, and that is complete -- there is no third value to
handle.

The null branch skips `completed_test_round` for a reason that is logical rather
than stylistic. A round's met/not-met cannot be computed at all for a student
who did not finish it -- **unless the criteria is OR**:

- `AND` needs every measure, so a skipped measure leaves the result
  **indeterminate**. There is no way to know whether the student would have met
  it, so the round cannot be credited.
- Null (OR) needs any measure, so one passing measure settles the round. What
  was skipped cannot change the answer.

Measured on AY2025, among students whose round criteria passed but who did not
complete the round: **374 `AND` rows score 0, and 222 null rows score 1.** Do
not "simplify" the gate away -- it is load-bearing under `AND`.

Worth carrying into any reporting conversation: those 374 are not failures, they
are **unmeasurable**. `met_pm_round_overall_criteria` cannot say so -- 0 means
both "did not meet" and "could not be evaluated" -- so `pm_round_status` sits
beside it and labels them `Round Incomplete`. With `AND` network-wide from
SY26-27 that population only grows, which is why T&L's categories keep _Not
Tested_ separate from _Below_ rather than folding it in.

An earlier version of this section called the missing `'OR'` branch an inert
gap, on the evidence that zero AY2025 rows carry `'OR'`. That was literally true
and thoroughly misleading -- the OR behaviour is live, under a different
spelling.

## all_assessments changed grain -- every consumer must NAME its model_type

**The highest-value thing to check when touching anything downstream of
`int_amplify__all_assessments`.** It now emits one row per data method (`BM` /
`Internal` / `Aimline`), so a consumer that does not filter `model_type` either
double-counts or is correct only by accident.

Three consumers broke on this and were fixed on the aimline branch. All three
failed silently -- no error, no failing test, just multiplied rows:

| Consumer                              | What it had               | Effect                                                            |
| ------------------------------------- | ------------------------- | ----------------------------------------------------------------- |
| `rpt_tableau__dibels_dashboard` PM    | nothing                   | **4x** -- 2x on the score join, 2x on roster                      |
| `int_amplify__pm_met_criteria`        | nothing                   | 72,970 rows from 17,004 distinct score keys                       |
| `rpt_gsheets__dibels_pm_goal_setting` | `period in ('BOY','MOY')` | one coincidence from averaging PM into a benchmark starting score |

Measured precisely rather than estimated: on AY2025 the PM score attach has
**exactly 2 rows per (year, season, round, measure, student) on 36,507 of 36,507
groups**, and the roster **2 per (year, grade, season, round, student) on 24,594
of 24,594**. There is no partial version of this bug -- if a join is unscoped it
doubles, everywhere.

**Every remaining consumer is safe for a reason it does not state.** That is the
part to internalise, because each of these is one refactor from breaking:

| How it survives                                                  | Which                                                                                                                                       |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Filters `assessment_type` explicitly                             | `rpt_gsheets__dibels_bm_goals_calculations`, `dim_assessments`, `dim_assessment_administrations`, `fct_assessment_scores_enrollment_scoped` |
| Filters `measure_standard = 'Composite'`, which PM never carries | `int_extracts__student_enrollments_subjects`, `rpt_tableau__mtss_rti`, `rpt_gsheets__mtss_rti`, `rpt_gsheets__kippmiami_payout_roster`      |
| Filters `measure_name = 'Composite'`, which PM never carries     | `int_topline__dibels_benchmark_weekly`                                                                                                      |
| Benchmark seasons never equal PM seasons (`BOY` vs `BOY->MOY`)   | the dashboard's own BM branch, and its composite read                                                                                       |
| `overall_probe_eligible` is null on EOY rows                     | the EOY exclusion in `pm_goal_setting`                                                                                                      |

None of those was left unscoped carelessly -- they predate `model_type`. But
"correct because a composite filter happens to exclude PM" is not a design, and
the fix when you touch one is to state the scope, not to rely on the coincidence
holding.

**How to audit it in one command:**

```bash
cd src/dbt/kipptaf
for f in $(grep -rl int_amplify__all_assessments models --include=*.sql \
           | grep -v 'int_amplify__all_assessments.sql'); do
  printf '%-3s %-3s  %s\n' "$(grep -c assessment_type "$f")" \
    "$(grep -c model_type "$f")" "${f#models/}"
done | sort -k2 -n
```

A zero in the second column is not automatically a bug -- check what else scopes
it -- but it is always worth reading.

**Corollary for the aimline sibling:** it reads `all_assessments` too, and it
must say `model_type = 'Aimline'` rather than infer it from whichever column
happens to be null on the internal method. `overall_probe_eligible` will not
serve: it is `'Yes'` on every Internal PM row and the composite level on every
Aimline one, so it discriminates -- until someone changes what the aimline
branch projects into it.

## TODO -- shared active/current schools model needs more eyes

Deferred deliberately; do not build it as a side effect of DIBELS work.

Three consumers each resolve "which schools count" independently, and they want
different things: **FRESH** wants schools it is _recruiting for_
(`finalsite_recruitment_year`, including Finalsite-only schools with no SIS rows
yet, entered by SRE through the intake in the fresh-dashboard skill's Step 0c);
**DIBELS** wants all years for Benchmark and the current year for PM (for now);
**CSGF** wants past and current. A shared `is_active` boolean would be wrong for
three of those four cases -- what is actually common is region resolution plus a
school-by-academic-year presence relationship each consumer filters itself.

Findings to carry in, so the next person doesn't re-derive them:

- `int_students__schools` (Charlie, #4731 / PR #4775) is the SIS-agnostic school
  spine and already has five mart consumers, but it is deliberately INCLUSIVE
  (an anti-join shape chosen so the `999999` graduated-students sentinel
  survives) and its Focus branch carries neither `schoolcity` nor
  `state_excludefromreporting`. Build on it; don't build beside it.
- `max_syear is null` (Focus) is the only active-school predicate in the repo,
  and it exists in exactly one place: `int_tableau__fresh_enrollment_scaffold`.
- **`min_syear` is NULL for all seven Miami schools** -- `max_syear` is a CLOSE
  marker only, so Focus metadata cannot tell you when a school opened. Per-year
  presence has to come from data (`int_students__calendar_day` carries schoolid
  x academic_year for both SISes).
- Region without `schoolcity`: `{{ extract_region(...) }}` on
  `_dbt_source_project`, which yields values matching `reporting__terms.region`
  exactly.
- FRESH's `finalsite_new` overlay must NOT move into a shared model -- it
  depends on a human intake step and deliberately includes schools with zero SIS
  presence.
