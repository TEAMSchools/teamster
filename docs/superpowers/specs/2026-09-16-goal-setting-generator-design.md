# Goal-setting generator: school goals and student buckets from a rules file

Design for [#5335](https://github.com/TEAMSchools/teamster/issues/5335). Settled
in brainstorming on 2026-09-16. Context:
`.claude/scratch/2026-09-15-iready-k2-goals/HANDOFF.md` and the methodology
digest `sy27-goal-setting-reference.md` in the same folder.

## Problem

Every fall the data team sets a school goal for each school, grade, and subject,
and places each student in Bucket 1 to 4. The stored results live in two places:
school and region goals in the academic goals Google Sheet
(`stg_google_sheets__assessments__academic_goals`), and buckets in PowerSchool
special programs named `Bucket N - Subject`, read by
`int_extracts__student_enrollments_subjects.nj_student_tier`. Every dashboard,
the tier roster sheet, and the Illuminate programs feed read those stored
values.

The tool that produced them was `rpt_tableau__academic_goals_rollup`. It
recomputes goals and buckets live from the roster. Its `student_tier_calculated`
column has no downstream consumer; it was always a proposal that the data team
copied into PowerSchool. Three things broke that arrangement:

1. Rules now differ by region, grade band, and year. SY27 New Jersey grades 1 to
   2 math count "Mid or Above" as proficient (crosswalk level 5) where the model
   encodes "Early On or better" (level 4 or higher). Paterson gains a Bucket 3.
   Bucket 3 gains a stretch-growth rule. The model holds one CASE expression for
   all of this.
2. Regions run at different times. Miami runs weeks before New Jersey, and New
   Jersey grades 3 and up wait for state scores and roll out around MOY. A live
   model has no notion of a rollout date.
3. The SY27 grades 1 to 2 math goals were produced by a one-off script outside
   the repo (`nj_k2_math_goals.py`). It is not version-controlled, nobody else
   can run it, and a school leader asking "why is this student in Bucket 2" gets
   no answer from it.

Bucket additions after rollout go through a Google Form
(`1h2gdT7GjEVMfeWuW172V3-a3FjNj_V6eobAdZ8UWE4s`, via
`int_google_forms__form_responses`). Today an ad hoc query pivots the responses,
maps them to PowerSchool program ids, anti-joins existing enrollments, and
produces an import file. It has no cap enforcement and does not detect a student
who already holds a different bucket for the same subject.

## Decision

Build a Python generator whose rules are data in the repo. The stored values
stay the source of truth; the generator proposes them, explains them, and a dbt
view reconciles them.

- **Frozen annual proposal, not a live recompute.** One run per rules group
  produces that group's school goals and buckets as of a rollout date. The
  Tableau rollup stops computing buckets and reads stored values (PR 4).
- **Rules in YAML, one file per academic year.** Region targets stay in the
  goals sheet so Teaching and Learning keeps ownership of the numbers. The
  strategy choices per region, grade range, and subject live in
  `config/goal_setting/ay<year>.yaml`.
- **Python-first.** SQL only fetches flat student rows per assessment source.
  Classification, the bubble parameter, ranking, buckets, and form amendments
  are pure functions over plain records, each with fixture tests.
- **The form is the only amendment channel.** No overrides file. The amend mode
  reads the form from the warehouse.
- **Local run under `uv`.** No Dagster job in this phase.

Rejected: a dbt seed of rules joined by the rollup (bucket rules like "top N by
score with ties admitted" are not join keys, so it becomes the current CASE with
an extra table); SQL-first strategy fragments (tests would need a warehouse and
per-student explanations are awkward); a Python module per year (least
structure, hardest to diff across years).

## Design

### Layout

```text
config/goal_setting/
  ay2026.yaml                 rules for academic_year 2026 (SY27)
  ps_programs.yaml            PowerSchool program id crosswalk, region x subject x bucket
src/teamster/goal_setting/
  __main__.py                 CLI: rollout | amend, --year, --group/--region, --out
  config.py                   Pydantic models, YAML load, strategy registry validation
  adapters/                   one module per assessment source; SQL + row typing
  rules/
    classify.py               proficient / approaching / below from levels
    school_goal.py            bubble_parameter | blanket | flat
    bucket2.py                top_approaching_to_move
    bucket3.py                remaining_approaching | stretch_reachers | remaining_approaching_or_stretch | bottom_pct_rank | none
    amend.py                  form rows -> validated additions, rejections
    invariants.py             one bucket per student x year x subject, cap checks
  outputs.py                  CSV writers, explain rows, manifest
tests/goal_setting/
  fixtures/                   tiny rosters; SY27 aggregate CSVs from the one-off
  test_*.py                   one file per rules module, cases named after doc rows
```

Dependencies already present transitively: `google-cloud-bigquery`, `pydantic`,
`pyyaml`. No new top-level dependency. No pandas; records are dataclasses or
dicts.

### Rules file

```yaml
academic_year: 2026
groups:
  - name: nj_math_1_2
    regions: [Newark, Camden, Paterson]
    grades: [1, 2]
    subject: Math
    rollout_date: 2026-10-15
    source: iready_boy
    levels:
      proficient: [5]
      approaching: [4]
    target: { from: goals_sheet, column: grade_band_goal }
    school_goal: bubble_parameter
    bucket2: { strategy: top_approaching_to_move, ties: admit }
    bucket3: { strategy: remaining_approaching_or_stretch }
    amendments: { max_per_school_grade_subject: 3, to_buckets: [2] }
```

Each group is independent. `rollout_date` is the date the group's proposal is
frozen; the amend mode keeps form rows submitted after it. A region that needs a
different rule gets its own group. A year that changes a definition gets a new
file, and the diff between two years' files is the change log.

Loading validates: every strategy name exists in the registry (failure lists the
valid names); every parameter a strategy needs is present; grade ranges within a
region and subject do not overlap; the `ps_programs.yaml` crosswalk is unique on
region plus program id. Validation runs as a pytest so a bad file fails CI.

Strategy vocabulary needed now, from the methodology digest and the current
rollup:

| Slot        | Strategies                                                                                                                |
| ----------- | ------------------------------------------------------------------------------------------------------------------------- |
| source      | `iready_boy`, `njsla_prior_year`, `fast_pm3_prior_year`, `fast_pm1`, `star_boy`, `star_spring_prior`, `psat` (grade 11)   |
| school_goal | `bubble_parameter`, `blanket`, `flat`                                                                                     |
| bucket2     | `top_approaching_to_move` (`ties: admit` or `strict`), `none`                                                             |
| bucket3     | `remaining_approaching`, `stretch_reachers`, `remaining_approaching_or_stretch`, `bottom_pct_rank` (grade 3 rule), `none` |

PR 1 implements `iready_boy`, `bubble_parameter`, `blanket`,
`top_approaching_to_move`, `remaining_approaching`, `stretch_reachers`,
`remaining_approaching_or_stretch`, and `none`. The rest are registry entries
that raise `NotImplementedError` naming the PR that will add them, so a rules
file can reference them and fail loudly.

### Adapters

An adapter returns one record per student and subject for a group: student
number, region, school, grade, tested flag, projected level, projected score,
stretch level, and the assessment name. The roster comes from
`int_extracts__student_enrollments_subjects` filtered `rn_year = 1`,
`enroll_status = 0`, not exempt from state testing, matching the rollup's
filters. `iready_boy` joins `int_iready__diagnostic_results` at
`test_round = 'BOY'`, `rn_subj_round = 1`, and maps
`overall_scale_score + annual_typical_growth_measure` and
`+ annual_stretch_growth_measure` through `stg_google_sheets__iready__crosswalk`
(destination `i-Ready`). That direct addition is exact for a baseline diagnostic
and sidesteps the staging defect in #5316; a TODO at the derivation site names
#5317 for the switch back to `level_number_with_typical`.

### Rules

All pure functions. Inputs and outputs are lists of records; nothing reads the
warehouse.

- `classify(records, levels)` sets `is_proficient`, `is_approaching`, `is_below`
  from the projected level and the group's `levels`.
- `school_goal.bubble_parameter(records, target)`: per region and group,
  `bp = round((sum tested * target - sum proficient) / sum approaching, 2)`; per
  school and grade, `n_to_move = ceiling(n_approaching * bp)` and
  `goal = (n_proficient + n_to_move) / n_tested`. Matches the rollup and the
  one-off to the cent. `blanket` sets every school's goal to the region target
  and `n_to_move` to the count needed to reach it. `flat` reads a per-school
  number from the goals sheet.
- `bucket2.top_approaching_to_move(records, n_to_move, ties)`: rank approaching
  students by projected score within school and grade; `admit` uses `rank()`
  semantics so ties at the cutoff all enter, `strict` uses `row_number()` with
  student number as the tiebreak.
- `bucket3.*` as named. `remaining_approaching_or_stretch` is what the SY27
  one-off built: remaining approaching students plus anyone not already placed
  whose stretch level is proficient.
- Bucket 1 is every proficient student; Bucket 4 is everyone else, untested
  included.

Every function also returns a reason string per student, for example
`approaching, projected 409, rank 7 of 12 to move`.

### Invariants

`invariants.py` runs before any file is written and aborts the run on failure:

- Exactly one bucket per student, academic year, and subject in the output.
- Every school and grade in the roster has a goal row.
- Region roll-up of school goals lands within 0.01 of the region target for
  `bubble_parameter` groups (the per-school ceiling overshoots slightly by
  design).
- Amendments per school, grade, and subject do not exceed the group's cap.

### Outputs

All files land in the folder named by `--out`. None are committed.

| File                  | Shape                                                                                                             | Audience                                |
| --------------------- | ----------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| `school_goals.csv`    | goals sheet columns: Academic_Year, School_ID, Grade_Level, Illuminate_Subject_Area, School_Goal, Grade_Band_Goal | paste into the goals sheet              |
| `ps_programs.csv`     | student_number, region, programid, enter_date, exit_date                                                          | PowerSchool special program import      |
| `student_buckets.csv` | one row per student and subject with every intermediate value and the final bucket                                | data team, local only, PII              |
| `frozen_buckets.csv`  | academic_year, student_number, subject, bucket, group, rollout_date                                               | paste into the frozen-buckets sheet tab |
| `explain.csv`         | student_number, subject, bucket, reason                                                                           | answering stakeholder questions         |
| `manifest.json`       | rules file SHA, crosswalk SHA, group name, rollout date, query text, row counts, run timestamp                    | reproducibility                         |

Enter and exit dates derive from the academic year (July 1 to June 30). The
rollout mode anti-joins `int_powerschool__spenrollments` so a re-run after a
partial load emits only the rows still missing. The terminal prints the school
summary and region roll-up tables the one-off prints today.

### Amend mode

`uv run python -m teamster.goal_setting amend --year 2026 --group nj_math_1_2 --out <folder>`

1. Read the form responses for the form id in the rules file, pivot
   `student_number`, `subject`, `bucket`, keep the latest response per student,
   year, and subject, and keep rows submitted on or after the group's
   `rollout_date`.
2. Join to the roster for region, school, and grade. Drop and report rows for
   students not on the roster.
3. Reject a request whose target bucket is not in the group's `to_buckets`.
4. Look up every bucket program the student already holds for that subject and
   year. A request for a bucket the student already holds is a no-op. A request
   for a different bucket is rejected with the existing bucket named, unless the
   form row is marked as a move, in which case the delta carries an exit row for
   the old program.
5. Count accepted additions per school, grade, and subject against the rollout
   run's `frozen_buckets.csv` plus prior accepted additions; reject the ones
   past the cap in submission order.
6. Write `ps_programs_delta.csv`, `rejected.csv` (student_number, subject,
   requested bucket, reason, requester, submitted date), an updated
   `explain.csv` with reasons like
   `added by form, requested by X on date, 2 of 3 for school S grade G`, and a
   manifest.

Running amend twice yields the same delta until new form rows arrive.

### PowerSchool program crosswalk

`config/goal_setting/ps_programs.yaml`, verified against
`int_powerschool__spenrollments` on 2026-09-16. Program ids are scoped to each
region's PowerSchool instance, so Camden and Newark both using 7374 is correct.

| Region   | B1 ELA | B1 Math | B2 ELA | B2 Math | B3 ELA | B3 Math |
| -------- | -----: | ------: | -----: | ------: | -----: | ------: |
| Camden   |   7376 |    7375 |   7173 |    7174 |   7373 |    7374 |
| Newark   |   7578 |    7577 |   7374 |    7375 |   7573 |    7574 |
| Paterson |   1633 |    1634 |   1635 |    1636 |   1637 |    1638 |

Bucket 4 has no program; the enrollments model defaults students without one to
Bucket 4. Miami has no rows in that view. Where Miami buckets are stored after
the Focus cutover is an open item; Miami rows enter the crosswalk only once that
is confirmed.

### Reconciliation view (PR 3)

`rpt_tableau__goal_bucket_reconciliation` joins the frozen-buckets sheet tab (a
new tab on the academic goals spreadsheet, staged as
`stg_google_sheets__assessments__frozen_buckets`), the bucket form responses,
and `int_extracts__student_enrollments_subjects.nj_student_tier`. One row per
student, year, and subject with a class:

- `match`: stored tier equals the frozen bucket.
- `added_by_form`: stored tier differs and an accepted form row explains it.
- `changed_outside`: stored tier differs and no form row explains it.
- `multiple_buckets`: the student holds more than one bucket program for the
  subject and year in PowerSchool.
- `over_cap`: the school, grade, and subject exceed the amendment cap.

This is the answer to "why is this student in Bucket 2," and it surfaces
existing dirty data once so it can be cleaned at the source.

### Tableau rollup rewrite (PR 4)

`rpt_tableau__academic_goals_rollup` keeps its roster and live proficiency
columns and its contract, but takes `grade_band_goal`,
`percent_with_growth_met`, `n_bubble_to_move`, and `bubble_parameter` from the
goals sheet's stored school rows, and `student_tier_calculated` becomes the
stored `nj_student_tier`. The bucket CASE expressions are removed. Details are
settled in that PR after PRs 1 to 3 land and the SY27 values are stored.

## Verification

- **Unit tests** per rules module, cases named after the methodology row they
  implement, with 5 to 10 student fixtures. Examples:
  `test_bucket2_ties_at_cutoff_all_admitted`,
  `test_bucket3_stretch_reacher_below_approaching_enters`,
  `test_one_bucket_per_student_year_subject_aborts_on_duplicate`,
  `test_amend_rejects_second_bucket_names_existing`.
- **Regression fixture**: `nj_k2_math_school_goals_ay2026.csv` and
  `nj_k2_math_region_rollup_ay2026.csv` from the one-off, checked in under
  `tests/goal_setting/fixtures/`. The rollout mode over a recorded roster
  fixture (student numbers replaced by sequential ids) reproduces them exactly.
- **Concordance**: for a group where the old rollup and the new rules agree by
  design (SY26 Newark grades 1 to 2 math under the "Early On or better" rule),
  bucket counts match the rollup's, proving the migration changed only what the
  rules file says.
- **Config validation** as a pytest over every file in `config/goal_setting/`.
- **Review handoff**: each PR ends with a reading order and a per-file "what to
  check" list, since Python review is the heavy part for the requester.

## Rollout order

1. PR 1: package, `ay2026.yaml` with the New Jersey K to 2 math groups,
   `ps_programs.yaml`, rollout mode, tests. Closes the immediate SY27 need.
2. PR 2: amend mode, replacing the ad hoc form query.
3. PR 3: frozen-buckets sheet tab, its staging model, and the reconciliation
   view.
4. PR 4: Tableau rollup rewrite to read stored values.

Grades 3 and up, grade 9, grade 11, and Miami get rules entries as their sources
and decisions land, each a small PR adding YAML rows and, where needed, one
adapter.

## Open items

- Kindergarten bucket rules under the blanket goal: the K row of the doc defines
  Bucket 3 as stretch-reachers only; the production model uses remaining
  approaching. Rules file records whichever T&L confirms.
- The +3 amendment rule: to Bucket 2 only, or to Buckets 2 and 3. The doc says
  both. `to_buckets` in the rules file records the answer.
- Where Miami buckets are stored after the Focus cutover.
- Whether "Early On or better" is still reported alongside the Mid/Above goal
  for grades 1 to 2. Affects PR 4 only.

## Out of scope

- A Dagster job or scheduled run. The generator is a terminal tool.
- Automated small-cell suppression on any output.
- Changing who enters region targets in the goals sheet.
- Retiring `rpt_tableau__academic_goals_rollup`; PR 4 rewrites it in place.
