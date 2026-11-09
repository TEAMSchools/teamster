# Performance bands dimension: design

Issue: #5573. Asana: `dim_assessments` (Data Marts + Semantic Layer), PR C under
"DDI Suite". Build issue for the dashboard: #6192.

## Why

An Illuminate or Focus Assessments score carries a band number, a band label and
a mastery flag, but nothing says what the band means. Band sets differ in cut
points, in band count and in which band starts mastery, so "band 4" is mastery
on one test and not on another. Two needs follow:

- The DDI Suite's DKI View groups scores into Below, Approaching and At/Above,
  counted from where mastery starts, and flags Far Below. Cube cannot reproduce
  either today. The workbook guesses where mastery starts from school level, and
  that guess disagrees with the band set's own mastery flag on 1.7% of 2026-27
  scores.
- The Cube chat assistant should answer "what counts as mastery on this test?"
  from live data. Today the answer is a hand-kept table in
  `src/cube/mcp/project_knowledge/assessment-cube-reference.md` that has already
  drifted once.

What needs the band set or cut points, beyond whether a student mastered
(decided 2026-11-02, #5573 comment of that date, answer 1):

- whether a student moved between bands across different assessments;
- the percent of students below or far below, or far below alone.

This design serves both.

## Goals

1. Every Illuminate and Focus Assessments score row in Cube says which band set
   scored it and where its band sits relative to that set's mastery band.
2. Cube can reproduce the DKI View's 3 levels and its Far Below flag, read from
   each band set instead of from school level.
3. Cube can show whether a student moved between bands across different
   assessments: `mastery_level` means the same thing on every band set, so a
   student's levels on 2 assessments compare directly, where band numbers do
   not.
4. Cube reports the percent of students below or far below, and far below alone.
5. Cube can answer "what counts as mastery on this test?": the band set's name,
   its cut points, its mastery band and its mastery cut.
6. The hand-kept band-set tables leave `assessment-cube-reference.md`.
7. The 2 open field subtasks on the `dim_assessments` Asana task are closed:
   - State test code / name: already in `dim_assessments` and Cube. For state
     rows, `module_code` holds the test code (`ELA05`, `ALG01`, `MATGP`) and
     `title` holds the test name (`NJSLA`, `NJGPA`, `FAST`, `EOC`). The Cube and
     dbt descriptions of both members say so. No new column.
   - QBL: retired on 2026-09-30 (DDI Suite task). The subtask is closed as
     retired. Nothing is built.

## Non-goals

- The by-position "Target+" grouping on 8 DDI Suite band-distribution sheets.
  Anthony's Asana task (under `dim_assessments`) asks to retire it on the
  dashboard.
- Tableau's what-if re-banding by parameter cut points ("Performance Band -
  Override").
- State tests, i-Ready, DIBELS, STAR and FAST state scores. They have their own
  scales and none uses a band set.
- Deciding which band set Illuminate standards should use (#6221, Asana "Decide
  which band set ..."). Each score row keeps the set Illuminate scored it on.
- Removing `performance_band_label_number` or `proficiency_level` from the fact.
  Cube reads both today.
- A precomputed movement column ("previous test", "change in level"). The ask is
  movement between different assessments, which a user picks; a fixed "previous
  test" needs a sequencing rule nobody has decided.
- Test-level discipline (PR 2 on the Asana task, Nov 16) waits on its own
  decision.

## Anti-goals

- Comparing band numbers across band sets. A level must mean the same thing on
  every set, or it does not ship.
- A second copy of band logic that can drift from Illuminate or Focus. Cut
  points and the mastery flag come from the source tables on every build.

## Decided

- Scale: the DKI View's. At/Above is the set's mastery band and above;
  Approaching is the band directly below the mastery band; Below is every band
  under that. Far Below is band 1 when band 1 is not a mastery band. (Cristina,
  2026-11-05)
- Standards and reporting groups are leveled on their own band set, as
  `int_assessments__performance_bands` already scores them. (Cristina and
  Anthony, 2026-11-02)
- Focus Assessments mastery is `Level 3` and above on every band set. (Cristina
  and Anthony, 2026-11-02)
- Scope is everything in #5573 and the `dim_assessments` Asana task that is not
  listed under Non-goals, built and validated together. (Cristina, 2026-11-05)
- The Below and Far Below shares are percents of students, per the 2026-11-02
  answer. On 1 assessment's overall scores a student has 1 row, so the share
  equals the DKI's row average there.

## Facts the design rests on

Measured 2026-11-05.

- The fact draws Illuminate and Focus scores from
  `int_assessments__response_rollup`, which carries `source` and
  `performance_band_set_id` on every taken row. A band set id is unique only
  within its source: Focus ids would collide with Illuminate ids.
- 94 band sets score internal assessments: 90 Illuminate, 4 Focus. Every one
  cuts on percent correct, 0 to 100. None has every band flagged mastery, and
  none has no mastery band. (`AP4A/CCRS General`, which flags every band, scores
  no internal assessment.)
- On those 90 Illuminate sets: mastery starts at band 3 (21 sets) or later,
  never band 1 or 2; mastery runs contiguously to the top band; `label_number`
  runs 1 to N in cut-point order. Focus sets start mastery at band 3 (5 bands)
  or 6 (8 bands). So Approaching and Far Below never fall on 1 band, and Far
  Below always sits inside Below.
- Illuminate bands come from `int_illuminate__performance_band_sets` (one row
  per band, with `minimum_value`, computed `maximum_value`, `label_number` and
  `is_mastery`).
- Focus bands live in the focus package's `stg_focus__apex_band_levels` (built
  in `kippmiami_focus`; no band number, no mastery flag). The package's
  `int_focus__apex_results` derives the band number by ordering on `min_score`
  and the mastery flag as `Level 3` and above, inside a CTE. kipptaf has no
  source for either table today.
- 482 Illuminate standard rows (2 assessments) have no band set, by the existing
  rule that nulls a merged standard split across 2 sets. 3,097 Focus rows have
  no band set. Neither gets a band key.
- The DKI's school-level guess: on 2026-27 overall and standard rows it
  disagrees with `is_mastery` on 9,743 of about 573,000 rows.

## The shape (my calls, for the builder to keep or justify changing)

### A band dimension, one row per band

`dim_performance_bands`, one row per band in each band set any internal score
uses. Proposed columns, to be checked against the mart naming rubric:

| Column                           | Meaning                                              |
| -------------------------------- | ---------------------------------------------------- |
| `performance_band_key`           | PK: hash of source, band set id, band number         |
| `performance_band_set`           | The band set's name                                  |
| `band_label`                     | The band's label, as the source spells it            |
| `band_number`                    | Position in the set, 1 = lowest                      |
| `band_count`                     | Bands in the set                                     |
| `minimum_score`, `maximum_score` | The band's percent-correct range                     |
| `is_mastery`                     | The source's mastery flag for this band              |
| `mastery_band_number`            | The set's lowest mastery band                        |
| `mastery_minimum_score`          | The set's mastery cut, in percent correct            |
| `mastery_level`                  | `At/Above`, `Approaching` or `Below` (Decided above) |
| `is_far_below`                   | Band 1, when band 1 is not mastery                   |

A band, not a band set, is the grain because every level is a property of a band
within its set: the fact needs 1 key and no level logic. Set-level attributes
repeat on each band row.

### Where the logic lives

- A domain intermediate unions Illuminate and Focus bands at band grain, keyed
  by source, and computes the set-level and level columns. The dim reads it and
  keeps the sets internal scores use.
- Focus band numbers and the mastery flag move out of the CTE in the focus
  package's `int_focus__apex_results` into a package model at band grain, which
  both `int_focus__apex_results` and kipptaf read. One home for the rule. This
  is a package change that kipptaf reads through a new `sources-kippmiami.yml`
  entry and union wrapper, so CI needs the `zz_stg_kippmiami_focus` copy seeded
  (a shared staging write).

### The fact

`fct_assessment_scores_enrollment_scoped` gains `performance_band_key`, hashed
from the same 3 inputs, null where the row has no band set or no band (not-taken
rows, the merged standards, Focus rows with no set, and every non-internal
source). It is a structural add: no existing hash changes. The fact is a table
mart, so the edge goes under `config.meta.foreign_key`.

### Cube

- A `performance_bands` cube over the dim, joined many-to-one from
  `student_assessment_scores` on `performance_band_key`, and included in
  `student_assessment_scores_view`.
- Every dim column above except the key is a dimension. Each Cube description
  matches its dbt description.
- 2 measures: the percent of students with a Below score (Far Below included),
  and the percent with a Far Below score, each over students with a banded score
  in the slice. Both count distinct students, as `count_students` does.
- The Cube text on `performance_band_label_number` and `is_mastery` points to
  the new members.
- `mastery_level`'s `ai_context` says it compares across assessments and band
  numbers do not: to see whether a student moved between bands on 2 assessments,
  compare `mastery_level`, and name both assessments. The existing view text
  still applies: any growth figure is analyst-built.
- `mastery_level` stays out of the `proficiency_rollup` pre-aggregation, as
  `proficiency_level` and `is_mastery` do today (they multiply rollup rows,
  #5557). The validation run records query time; a slow result becomes a
  follow-up under #5557. (My call.)
- "What counts as mastery on this test?" is answered through
  `student_assessment_scores_view`, so it shows the band sets scored at the
  viewer's own schools, under the view's row-level access. No separate view over
  the dim. (My call.)

### Guard tests

The level rule assumes 3 things the data holds today. An `error` test on the
domain intermediate fails the build if a set breaks any of them, so a new
Illuminate set cannot silently mislevel scores:

- every set has at least 1 mastery band, and its mastery bands run contiguously
  to the top band;
- band numbers run 1 to N in cut-point order;
- mastery starts at band 3 or later, so Approaching and Far Below never share a
  band. (If a set ever starts at band 2, the rule needs a decision, not a code
  guess.)

### The reference file

Delete both interim band-set tables (Illuminate and Focus Assessments) from
`assessment-cube-reference.md`, and any routing text that points to them.

## Validation

- `uv run dbt build --select` the changed models and their children: the dim's
  PK is unique; `assessment_key` stays unique; the fact's row count is
  unchanged.
- `performance_band_key` is populated on every fact row that has a band number,
  and on no other row.
- For a sample of sets, `mastery_minimum_score` matches the source's lowest
  mastery band minimum.
- The cube-validation runbook on the DDI Suite, in the existing validation file
  on `cristinabaldor/test/claude-ddi-cube-validation` (its mastery comparisons
  on "DKI - Assessment Mastery Grid" and their proven causes already exist), run
  before merge against the dev build (`--fact-dataset`) and a local Cube:
  - "DKI - Assessment Mastery Bars": the percent of students per
    `mastery_level`. The sheet shows `COUNTD(student_number)` per 3-level band
    as a percent of total, the same basis as this design.
  - "DKI - Assessment Mastery Table": the Far Below share, which the sheet shows
    through Measure Values.
  - Expected difference: the rows where the workbook's school-level guess and
    the band set disagree. Prove that cause row by row with a `triage confirm`
    proof. The earlier causes (WPP, untagged modules, prior-year dates, section
    timing) apply to these rows too.
- The cut values (`minimum_score`, `mastery_minimum_score`) appear on no
  dashboard, so they are checked against the source band tables in the dbt
  build, not by the validator.

## Left to the builder

- Final column and model names, against the rubric in
  `.claude/rules/dbt-marts.md`.
- How the 2 Cube measures reach the joined cube's level (a measure filter on a
  joined member, or level flags carried another way), proven by a compile and a
  query.
- The domain intermediate's name and folder.
- Unit tests for the level rule, including a set whose mastery starts at band 3
  and an 8-band Focus set.
- Closing the 2 Asana subtasks (State test code / name with a pointer to
  `module_code` and `title`; QBL as retired) once the PR merges.

## Revision 2026-11-05: guard tests warn

Decided by Cristina while planning. The guard tests under _Guard tests_ run at
`warn`, not `error`: an `error` on the domain intermediate would skip the
dimension and the whole assessment fact downstream, so one oddly configured
Illuminate band set would stop every assessment dashboard refreshing. Instead, a
band set that breaks any of the 3 assumptions gets a null `mastery_level` and a
null `is_far_below` on every band. Its scores still load, with no level, and the
warning names the set to fix.

## Revision 2026-11-09: no band dimension

Decided on PR review (cbini). `dim_performance_bands` and its Cube cube are
dropped. The fact already carries the band label, band number and `is_mastery`,
and the asks need only the level, so `fct_assessment_scores_enrollment_scoped`
gains 2 columns, `mastery_level` and `is_far_below`, read from
`int_assessments__performance_band_union` on source, band set id and band
number. The union keeps the level rule and its guard and unit tests. Cube reads
both columns straight off the fact, and the share measures keep their names.

Goal 5 and goal 6 are withdrawn. Cut points, set names and mastery cuts stay in
`assessment-cube-reference.md`: no DDI view and no stakeholder ask needs them in
Cube.
