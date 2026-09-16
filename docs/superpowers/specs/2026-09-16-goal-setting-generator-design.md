# Goal-setting generator: school goals and student buckets from a rules file

Design for [#5335](https://github.com/TEAMSchools/teamster/issues/5335). Settled
in brainstorming on 2026-09-16 and revised the same day after a five-frame
design review. Context: `.claude/scratch/2026-09-15-iready-k2-goals/HANDOFF.md`
and the methodology digest `sy27-goal-setting-reference.md` in the same folder.

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
produces an import file. It has no cap enforcement, trusts the form's subject
and grade fields, and does not detect a student who already holds a different
bucket for the same subject.

## Decision

Build a Python generator whose rules are data in the repo. The stored values
stay the source of truth; the generator proposes them, explains them, and reads
them back to verify the load.

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
  reads the form from the warehouse and validates it against the roster.
- **Every run is checkable.** A run saves its inputs, commits a non-PII
  manifest, diffs itself against the prior run before writing, and a
  `verify-load` command reads the stored sheet and PowerSchool state back and
  diffs them against the run. Manual paste and import steps stay, but each one
  is followed by a check.
- **Local run under `uv`.** No Dagster job in this phase.

Rejected: a dbt seed of rules joined by the rollup (bucket rules like "top N by
score with ties admitted" are not join keys, so it becomes the current CASE with
an extra table); SQL-first strategy fragments (tests would need a warehouse and
per-student explanations are awkward); a Python module per year (least
structure, hardest to diff across years); goals as a dbt seed (moves target
ownership away from Teaching and Learning); writing to PowerSchool through its
API (removes the human checkpoint before a network-visible change); a continuous
score or an optimizer in place of the four buckets and the bubble parameter
(every consumer reads four labels, and concordance with the current method is an
acceptance test).

## Design

### Layout

```text
config/goal_setting/
  ay2026.yaml                 rules for academic_year 2026 (SY27)
  ps_programs.yaml            PowerSchool program id crosswalk, region x subject x bucket
  manifests/ay2026/<group>.json   committed, non-PII record of each rollout run
src/teamster/goal_setting/
  __main__.py                 CLI: rollout | amend | verify-load | verify-crosswalk | show
  config.py                   Pydantic models (strict, extra fields forbidden), YAML load, strategy registry
  adapters/                   one module per assessment source; SQL + row typing + input archive
  rules/
    classify.py               proficient / approaching / below from levels
    school_goal.py            bubble_parameter | blanket | flat
    bucket2.py                top_approaching_to_move
    bucket3.py                remaining_approaching | stretch_reachers | remaining_approaching_or_stretch | bottom_pct_rank | none
    amend.py                  form rows -> validated additions, receipts
    freshness.py              completeness gate, runs between fetch and compute
    invariants.py             one bucket per student x year x subject, cap checks, region checks
  diff.py                     proposal vs prior manifest and prior output
  verify.py                   stored sheet and PowerSchool state vs run
  outputs.py                  single write call at the end; CSV writers, explain rows, manifest
tests/goal_setting/
  fixtures/                   tiny rosters; SY27 aggregate CSVs from the one-off
  test_*.py                   one file per module, cases named after doc rows
```

Dependencies already present transitively: `google-cloud-bigquery`, `pydantic`,
`pyyaml`. No new top-level dependency. No pandas; records are dataclasses or
dicts.

A test asserts that no module under `rules/` imports a warehouse client, so a
rule cannot read live data mid-run and break reproducibility.

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
    bucket3: { strategy: stretch_reachers }
    amendments: { max_per_school_grade_subject: 3, to_buckets: [2] }
    freshness: { min_tested_share: 0.85, roster_tolerance: 0.15 }
```

Each group is independent. `rollout_date` is the date the group's proposal is
frozen; the amend mode keeps form rows submitted on or after it. A region that
needs a different rule gets its own group. A year that changes a definition gets
a new file, and the diff between two years' files is the change log.

Loading validates: every strategy name exists in the registry (failure lists the
valid names); every parameter a strategy needs is present and no unknown
parameter is accepted, so a typo cannot fall through to a default branch; grade
ranges within a region and subject do not overlap; the `ps_programs.yaml`
crosswalk is unique on region plus program id, and not on program id alone,
because ids repeat across regions. Validation runs as a pytest over every file
in `config/goal_setting/` so a bad file fails CI.

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

An adapter returns one record per student and subject for a group: region,
student number, school, grade, tested flag, projected level, projected score,
stretch level, and the assessment name. Region is a required field on every
record, and every join, anti-join, and dedup in the pipeline keys on region plus
student number, never student number alone. The roster comes from
`int_extracts__student_enrollments_subjects` filtered `rn_year = 1`,
`enroll_status = 0`, not exempt from state testing, matching the rollup's
filters. `iready_boy` joins `int_iready__diagnostic_results` at
`test_round = 'BOY'`, `rn_subj_round = 1`, and maps
`overall_scale_score + annual_typical_growth_measure` and
`+ annual_stretch_growth_measure` through `stg_google_sheets__iready__crosswalk`
(destination `i-Ready`). That direct addition is exact for a baseline diagnostic
and sidesteps the staging defect in #5316; a TODO at the derivation site names
#5317 for the switch back to `level_number_with_typical`.

Before any rule runs, the adapter writes its fetched rows verbatim to
`<out>/inputs/<source>_<group>.csv` and returns their hash, row count, counts by
school and grade, and tested share by school and grade for the manifest. Those
files carry student numbers and scores and stay local. `--input <folder>`
replays a run from saved inputs instead of the warehouse, recomputes the hashes,
and aborts on a mismatch with the manifest in that folder. That is what makes
"why is this student in Bucket 2, three years later" answerable from one
archived run.

### Freshness gate

`freshness.py` runs between fetch and compute, before any rule, because the
point is to never compute from a truncated read. An empty or half-materialized
upstream table and a small group with few students look identical to the rules,
and both land every student in Bucket 4. The gate checks, per school and grade:

- Roster count against a baseline, within the group's `roster_tolerance`. The
  baseline is the prior year's manifest for the same group when one exists, and
  otherwise the same roster model's count at a pinned earlier date passed as
  `--baseline-date`. A hand-set floor is the fallback, not the primary.
- Tested share against the group's `min_tested_share`.

Two severities. A tested share or roster count below the hard floor is an error
and aborts with the school, grade, and both numbers printed. Drift outside
tolerance but above the floor is a warning, printed in the summary and recorded
in the manifest as `gate_warnings`, so a real enrollment change does not train
the team to override. `--force-stale` overrides an error and stamps
`gate_overridden: true` plus the failing rows into the manifest.

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
- `bucket3.*` as named. `stretch_reachers` is what the SY27 one-off built and
  what the decisions memo records; `remaining_approaching_or_stretch` stays in
  the registry for regions that keep the production rule.
- Bucket 1 is every proficient student. Bucket 4 is everyone else, recorded as
  two outcomes: `bucket_4_below` for tested students and `bucket_4_untested` for
  the rest. Both load to PowerSchool as no program. The split exists so a whole
  school reading "untested" shows a data failure on the face of the output even
  when the gate's thresholds were wrong.

Every function also returns a reason string per student, for example
`approaching, projected 409, rank 7 of 12 to move`.

### Invariants

`invariants.py` runs on the assembled proposal before any file is written and
aborts the run on failure. Every failure message names the school, grade, and
subject it fired on, and the offending count, never a bare stack trace.

- Exactly one bucket per region, student number, academic year, and subject.
- Every school and grade in the roster has a goal row.
- Region roll-up of school goals lands within 0.01 of the region target for
  `bubble_parameter` groups (the per-school ceiling overshoots slightly by
  design).
- Amendments per school, grade, and subject do not exceed the group's cap.
- No student's region or school differs between the frozen output being amended
  and today's roster without landing in the `moved_since_rollout` class (see
  amend mode).

### Diff and plan mode

Rollout is not idempotent by nature: the bubble parameter and the Bucket 2
cutoff recompute against a roster that gains late enrollments and loses
withdrawals, so a re-run can move a marginal student between buckets with
nothing showing it. Every rollout run therefore diffs its proposal against the
prior run for the same group and year before writing, and `--plan` stops after
the diff and the invariants with nothing written.

The diff works at two depths. Manifest to manifest always works, because
manifests are committed: it shows the bubble parameter and every school goal
moving, and the school by grade by bucket counts shifting. Student-level
transitions (from bucket to to bucket per school and grade) are computed when
`--against <folder>` points at a retained prior output folder on the operator's
disk. The operator sees a goals table, a bucket transition matrix with the
unchanged diagonal collapsed, a roster-churn line naming late enrollments and
withdrawals as the cause, and a one-line verdict: `no change`,
`additive only (N new students)`, or `RECLASSIFIES N students already loaded`.
The last verdict exits non-zero unless `--allow-reclassification` is passed, so
a re-run after a partial PowerSchool load cannot silently reclassify a student
who already holds a program.

The student-level baseline is an artifact the design never commits. If the prior
folder is gone, the diff degrades to counts, and a school holding at 12 Bucket 2
students with a different 12 inside looks unchanged. A committed per-student
hash would close that gap but is a pseudonymous identifier under the repo's
FERPA rule, so it is not done; the manifest records instead whether the last
diff ran at student depth.

### Outputs

All files land in the folder named by `--out`, by convention
`runs/ay2026/<group>/<timestamp>/`, which is gitignored. The manifest alone is
copied to `config/goal_setting/manifests/ay2026/<group>.json` and committed.

| File                  | Shape                                                                                                             | Audience                           |
| --------------------- | ----------------------------------------------------------------------------------------------------------------- | ---------------------------------- |
| `inputs/*.csv`        | adapter rows as fetched                                                                                           | replay and audit, local only, PII  |
| `school_goals.csv`    | goals sheet columns: Academic_Year, School_ID, Grade_Level, Illuminate_Subject_Area, School_Goal, Grade_Band_Goal | paste into the goals sheet         |
| `ps_programs.csv`     | region, student_number, programid, enter_date, exit_date                                                          | PowerSchool special program import |
| `student_buckets.csv` | one row per student and subject with every intermediate value and the final bucket                                | data team, local only, PII         |
| `explain.csv`         | region, student_number, subject, bucket, reason                                                                   | answering stakeholder questions    |
| `manifest.json`       | see below                                                                                                         | committed copy is the run's record |

The manifest holds: rules file SHA, crosswalk SHA, group, rollout date, run
timestamp, per-input file hash, row count, query text, counts by school and
grade, and tested share by school and grade; gate warnings and overrides; the
bubble parameter per region; every school goal; school by grade by bucket counts
including the two Bucket 4 outcomes; and the depth and verdict of the pre-write
diff. It contains no student identifiers. School by grade by bucket counts are
aggregates over a grade with no demographic slice, which the repo's FERPA rule
treats as not PII.

Enter and exit dates derive from the academic year (July 1 to June 30). The
rollout mode anti-joins `int_powerschool__spenrollments` on region, student
number, and program id so a re-run after a partial load emits only the rows
still missing. The terminal prints the school summary and region roll-up tables
the one-off prints today, under the diff tables.

### Amend mode

`uv run python -m teamster.goal_setting amend --year 2026 --group nj_math_1_2 --out <folder>`

1. Read the form responses for the form id in the rules file, pivot
   `student_number`, `subject`, `bucket`, keep the latest response per student,
   year, and subject, and keep rows submitted on or after the group's
   `rollout_date`.
2. Join to the roster on student number. The join must return exactly one
   region, school, and grade. Zero rows is `not_on_roster`. Two or more is
   `ambiguous_region`, rejected rather than deduped to the first match. On
   2026-09-16 no current-year student under the rollout filters appears under
   two regions or two schools, so this is a loud edge case, not a usability
   problem.
3. Validate the form's declared subject against the student's roster subjects
   and the declared grade against the roster grade before the request counts
   toward any cap, since the cap key is school, grade, and subject and the
   submitter controls two of the three. Mismatches are `subject_not_enrolled`
   and `grade_mismatch`, with both values printed.
4. Reject a request whose target bucket is not in the group's `to_buckets`
   (`bucket_not_allowed`).
5. Look up every bucket program the student already holds for that region,
   subject, and year. A request for a bucket the student already holds is
   `already_holds_bucket`. A request for a different bucket is rejected with the
   existing bucket named, unless the form row is marked as a move, in which case
   the delta carries an exit row for the old program. If the form has no move
   marker, moves are rejected and handled by hand; PR 2 records which.
6. Compare each frozen bucket row's region and school against today's roster. A
   student who moved after `rollout_date` is `moved_since_rollout`, excluded
   from cap counting at the new school, and listed for a human decision.
7. Count accepted additions per school, grade, and subject against the rollout
   manifest's counts plus prior accepted additions; reject the ones past the cap
   in submission order (`over_cap`).
8. Write `ps_programs_delta.csv`, `receipts.csv`, an updated `explain.csv`, and
   a manifest.

`receipts.csv` has one row per submitted form row, accepted or not, with the
class from the list above, a reason sentence written for a school leader, the
requester, and the submitted date. A `receipts/` subfolder holds one file per
school so the data team can send a school its own rows without filtering a
network-wide file. The terminal prints counts by class. The same class
vocabulary is used by `verify-load`.

`--plan` applies to amend as well: the delta and the receipts are more useful
printed before the import than discovered after it. Running amend twice yields
the same delta until new form rows arrive.

### Verify-load

`uv run python -m teamster.goal_setting verify-load --year 2026 --group nj_math_1_2 --run <folder>`

After the goals are pasted and the programs imported, this command reads the
stored state back and diffs it against the run. Goals: query
`stg_google_sheets__assessments__academic_goals` and compare every school row
against the manifest's school goals, reporting missing, extra, and mismatched
rows. Buckets: query `int_powerschool__spenrollments` for the group's regions,
year, and program ids, join the form responses, and classify every student in
the run's `student_buckets.csv` plus every student holding a bucket program:

- `match`: stored bucket equals the run's bucket.
- `not_loaded`: in the run, no program in PowerSchool.
- `added_by_form`: stored bucket differs and an accepted form row explains it.
- `changed_outside`: stored bucket differs and nothing explains it.
- `moved_region`: the student's region or school changed since rollout.
- `multiple_buckets`: more than one bucket program for the region, subject, and
  year.
- `over_cap`: the school, grade, and subject exceed the amendment cap.
- `unknown_program`: a bucket program id not in the crosswalk.

Manifest depth works from the committed manifest alone (goal rows and counts per
school, grade, and bucket). Student depth needs the run folder. The command
prints counts by class and writes `verify.csv` to the run folder; it exits
non-zero on anything but `match`, `added_by_form`, and an empty `not_loaded`.

`verify-load` replaces the frozen-buckets sheet tab and the dbt reconciliation
view from the first draft of this design. A dbt view can be added later if
someone outside the data team needs the classes in Tableau; it would source the
committed manifests, not a sheet.

### Verify-crosswalk and show

`verify-crosswalk` diffs `ps_programs.yaml` against
`int_powerschool__spenrollments` region by region and exits non-zero on a
program id that no longer resolves. Rollout and amend call it first, so a
renamed program aborts the run instead of producing an import file full of wrong
enrollments. It is also what the PR that adds Miami rows will paste as evidence.

`show --run <folder> --student <n>` replays one student's explain row from the
run's saved inputs. It is the command a data-team member types when a school
leader asks.

### PowerSchool program crosswalk

`config/goal_setting/ps_programs.yaml`, verified against
`int_powerschool__spenrollments` on 2026-09-16. Program ids are scoped to each
region's PowerSchool instance, so Camden and Newark both using 7374 is correct.
A fixture test asserts that 7374 under two regions loads and 7374 twice under
one region fails naming both entries.

| Region   | B1 ELA | B1 Math | B2 ELA | B2 Math | B3 ELA | B3 Math |
| -------- | -----: | ------: | -----: | ------: | -----: | ------: |
| Camden   |   7376 |    7375 |   7173 |    7174 |   7373 |    7374 |
| Newark   |   7578 |    7577 |   7374 |    7375 |   7573 |    7574 |
| Paterson |   1633 |    1634 |   1635 |    1636 |   1637 |    1638 |

Bucket 4 has no program; the enrollments model defaults students without one to
Bucket 4. Miami has no rows in that view. Where Miami buckets are stored after
the Focus cutover is an open item; Miami rows enter the crosswalk only once that
is confirmed.

### Tableau rollup rewrite (PR 4)

`rpt_tableau__academic_goals_rollup` keeps its roster and live proficiency
columns and its contract, but takes `grade_band_goal`,
`percent_with_growth_met`, `n_bubble_to_move`, and `bubble_parameter` from the
goals sheet's stored school rows, and `student_tier_calculated` becomes the
stored `nj_student_tier`. The bucket CASE expressions are removed. Details are
settled in that PR after PRs 1 to 3 land and the SY27 values are stored.

## Verification

- **Unit tests** per module, cases named after the methodology row or the
  failure they cover, with 5 to 10 student fixtures. Examples:
  `test_bucket2_ties_at_cutoff_all_admitted`,
  `test_bucket3_stretch_reacher_below_approaching_enters`,
  `test_one_bucket_per_student_year_subject_aborts_naming_school`,
  `test_amend_rejects_second_bucket_names_existing`,
  `test_amend_grade_mismatch_does_not_count_toward_cap`,
  `test_crosswalk_same_id_two_regions_loads`,
  `test_rules_module_imports_no_warehouse_client`,
  `test_plan_mode_writes_no_files`, `test_replay_from_inputs_is_byte_identical`.
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
   `ps_programs.yaml`, rollout mode with input archive, freshness gate,
   invariants, diff and plan mode, committed manifest, `verify-crosswalk`,
   `show`, tests. Closes the immediate SY27 need.
2. PR 2: amend mode with receipts, replacing the ad hoc form query.
3. PR 3: `verify-load`.
4. PR 4: Tableau rollup rewrite to read stored values.

Grades 3 and up, grade 9, grade 11, and Miami get rules entries as their sources
and decisions land, each a small PR adding YAML rows and, where needed, one
adapter.

## Open items

Data-team decisions:

- Kindergarten bucket rules under the blanket goal: the K row of the doc defines
  Bucket 3 as stretch-reachers only; the production model uses remaining
  approaching. Rules file records whichever Teaching and Learning confirms.
- The +3 amendment rule: to Bucket 2 only, or to Buckets 2 and 3. The doc says
  both. `to_buckets` in the rules file records the answer.
- Where Miami buckets are stored after the Focus cutover.
- Whether the form gets a "move" marker, or moves between buckets stay a manual
  step.
- Whether the generator emits exit and enter rows for a cross-region transfer or
  only reports it as `moved_since_rollout`.
- Whether "Early On or better" is still reported alongside the Mid/Above goal
  for grades 1 to 2. Affects PR 4 only.

Teaching and Learning process decisions, which this tool surfaces but does not
decide:

- Who resolves `changed_outside` and `multiple_buckets` findings, and by when.
  Without an owner the classes are a report, not a control.
- Whether a direct PowerSchool edit by a regional leader is a legitimate path,
  and if so how it is marked so `verify-load` can tell it from corruption.
- Whether the rules file needs an approval record beyond PR review.
- Whether a family or school can formally contest a placement, as distinct from
  requesting an amendment.

## Out of scope

- A Dagster job or scheduled run. The generator is a terminal tool.
- Automated small-cell suppression on any output.
- Changing who enters region targets in the goals sheet.
- Retiring `rpt_tableau__academic_goals_rollup`; PR 4 rewrites it in place.
- A dbt reconciliation view. `verify-load` covers the need; a view over the
  committed manifests can follow if Tableau visibility is asked for.
