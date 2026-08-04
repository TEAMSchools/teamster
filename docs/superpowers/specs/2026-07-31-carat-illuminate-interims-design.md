# CARAT Illuminate Practice Assessment Structure — Design

Refs [#4658](https://github.com/TEAMSchools/teamster/issues/4658)

## Context

The College Admission Readiness Assessments Tracker (CARAT) dashboard
(`college_admission_readiness_assessments_tracker_carat` exposure) no longer
reports Illuminate practice assessments. Practice/interim administration moved
to Winward, the data could not be pulled out of that platform, and interims were
dropped from reporting as a result. KIPP Foundation has now created four
practice SAT assessments in Illuminate for SY26-27, and KIPP Forward needs the
dashboard ready to accept scores before they land (expected the month after this
spec is written).

Student scores will not exist at implementation time — the first administration
is BOY, the month after this spec is written. Raw-to-scale-score conversions,
however, are in hand: Foundation supplied them and the data team is entering
them into the sheet now. The dashboard must therefore be built and verified with
no responses to query, which shapes the verification approach more than it
shapes the design.

The measure is the scale score, converted through the sheet. Illuminate's
performance bands are deliberately not used — see _Out of scope_.

Historical practice assessments must keep working. This is not a replacement.

## The four SY26-27 assessments

| `assessment_id` | `title`                                                | `scope`     | `subject_area` |
| --------------- | ------------------------------------------------------ | ----------- | -------------- |
| 226182          | `SAT-26-27-BOY Practice SAT-11th Grade-ReadingWriting` | `Benchmark` | `null`         |
| 226183          | `SAT-26-27-BOY Practice SAT-11th Grade-Math`           | `Benchmark` | `Mathematics`  |
| 226184          | `SAT-26-27-MOY Practice SAT-11th Grade-ReadingWriting` | `Benchmark` | `null`         |
| 226185          | `SAT-26-27-MOY Practice SAT-11th Grade-Math`           | `Benchmark` | `Mathematics`  |

All four are canonical (`assessment_id = canonical_assessment_id`, each its own
group), `is_internal_assessment = false`, `academic_year = 2027` /
`academic_year_clean = 2026`, `assessment_type = 'ibx'`, creator
`tadmin@illuminatekippteam.com`.

These are KIPP Foundation-created assessments, not KTAF-created ones. That is
consistent with the sparse metadata documented below and with the band sets
being named `Imported ...` — we should not expect KTAF's own field conventions
to hold on them, which is why the design reads subject, grade, and round from
the sheet instead.

## Findings that drive the design

### The historical designation mechanism cannot select the new assessments

`int_assessments__college_assessment_practice` filters
`where a.scope in ('ACT', 'SAT')`. All four new assessments carry
`scope = 'Benchmark'`, so the historical filter selects none of them.
Designation must be driven by an explicit `assessment_id` list, not by `scope`.

### Illuminate metadata is unreliable for the fields the joins need

- `subject_area` is `null` on both `ReadingWriting` assessments.
- `administered_at`, `administration_window_start_date`, and
  `administration_window_end_date` are `null` on all four, so administration
  season cannot be derived from dates and `int_assessments__response_rollup`'s
  `term_administered` join will not resolve.
- `scope` reports `Benchmark`, not `SAT`.

**Design principle:** the `act_scale_score_key` sheet is authoritative for
administration round, subject, and grade level. Illuminate is authoritative only
for assessment identity and student responses.

This is not new behavior — the equivalent AY2023-24 assessment 138850
(`SAT-23-24-BOY SAT-11th Grade-Reading/Writing`) also has `subject_area = null`
while the sheet carries `Subject = 'Reading and Writing'`.

### Performance banding exists upstream and stays unused

`int_assessments__response_rollup` already emits `percent_correct`,
`performance_band_label`, `performance_band_label_number`, and `is_mastery` for
every Illuminate assessment, including the four new ones (band sets 35058-35061,
`Imported SY26-27 KIPP Performance Levels`).

`int_assessments__college_assessment_practice` discards all of it, projecting
`points` only and converting through the sheet. **That stays as-is.** KIPP
Forward does not use Illuminate mastery levels for practice SAT reporting, so
the model is not widened to carry them. Recorded here only so a future reader
knows the data is available upstream and that ignoring it is a decision, not an
oversight.

### The sheet's inner join discards a data gap without failing

`int_assessments__college_assessment_practice` joins the sheet with
`inner join ... on a.assessment_id = ssk.assessment_id and a.points between ssk.raw_score_low and ssk.raw_score_high`.
One inner join serves two purposes — designation and conversion — so an
assessment cannot be designated without also having complete conversion rows.

The sheet holds only `Academic_Year = 2023` rows (12 assessment ids). Once
practice administration moved to Winward there was nothing later to enter, and
this join yields no rows for any subsequent year while raising no error. That
behavior is independent of why administration moved — it would discard the new
SY26-27 rows the same way, which is why it has to go.

### Two pre-existing defects the new work would inherit

Both verified against prod `int_assessments__college_assessment_practice`.

**1. `course_discipline` is `NA` on every math row.** The `CASE` tests
`a.subject_area in ('Math')`, but the raw Illuminate value is `Mathematics` —
the rename to `Math` happens in a sibling column of the same `SELECT`, and
BigQuery has no lateral column aliases, so the `CASE` sees the unrenamed value
and falls through to `else 'NA'`. Current state:

| `scope` | `subject_area` | `course_discipline` | rows  |
| ------- | -------------- | ------------------- | ----- |
| SAT     | `Math`         | `NA`                | 5,159 |
| ACT     | `Math`         | `NA`                | 2,238 |
| SAT     | `Reading`      | `ENG`               | 3,388 |
| SAT     | `Writing`      | `ENG`               | 4,244 |

No math row anywhere in the model has ever been tagged `MATH`. **Not fixed
here** — the fix is two words, but it moves 7,397 historical rows from `NA` to
`MATH`, which changes dashboard filter behavior and breaks the parity gate.
Deliberately left alone so this change stays behavior-preserving. See _Out of
scope_.

**2. The composite rows are duplicated.** Both composite branches are
`select distinct` over a partition, but project `course_discipline`,
`test_date`, and `test_month`, which vary within that partition. So each
student-round yields one composite row per distinct discipline. `Combined` holds
1,437 rows for 715 student-rounds; `Composite` holds 666 for 333. The duplicates
carry an identical `scale_score` (verified: exactly one distinct value per
student-round), and `int_tableau__college_assessment_roster_scores` aggregates
with `max(scale_score)`, so nothing is currently wrong downstream — but any
consumer that sums or counts double-counts. **The existing branches are not
fixed here** (halving those row counts would also break the parity gate); the
new branch simply must not reproduce the pattern, which it avoids by stamping
`course_discipline` constant. See _Out of scope_.

### Goal thresholds are computed off the official hub, which practice cannot reach

This is the largest gap between what is wanted and what exists.
`rpt_tableau__college_assessment_dashboard_benchmark_calcs` holds the only
threshold values in code — a literal `CASE` over 15 `benchmark_group` keys,
where `SAT_Combined_HS-Ready` is 890, `SAT_Combined_College-Ready` is 1010, and
`SAT_Combined_EA/ED-Ready` is 1200.

It reads `int_assessments__college_assessment`, which unions
`int_kippadb__standardized_test_unpivot` and `int_collegeboard__psat_unpivot`,
filters `test_type in ('ACT', 'SAT')`, and stamps `'Official' as test_type`.
There is no practice input and no `test_type` branch. So adding a `Practice`
branch to `int_tableau__college_assessment_roster_scores` gets practice rows
onto the roster but **not** next to a threshold.

Two ways to close it, and they are not equivalent:

- **Feed practice into `_benchmark_calcs`.** Reuses the existing thresholds
  directly. The hazard is `rn_highest = 1`, which picks each student's single
  highest score: with practice in the same pool, a practice result can outrank
  an official one and change reported college-ready attainment. That metric is
  used well beyond this dashboard, so this option is only safe if `test_type`
  partitions the ranking and every consumer filters on it.
- **Keep the pools separate** and compare practice totals against thresholds
  outside `_benchmark_calcs`, with `test_type` as a dimension so official
  attainment is arithmetically untouchable.

Recommendation: keep them separate. The thresholds are three integers; the
official-attainment metric is not worth risking to avoid duplicating them. This
also means the hardcoded-thresholds cleanup stays deferred rather than becoming
a prerequisite.

### There is no working 11th-grade precedent

Of the 12 sheet assessment ids, the two 11th-grade SAT ones (138849 Math, 138850
Reading/Writing) produce zero rows in
`int_assessments__college_assessment_practice` — they have complete conversion
rows in the sheet but zero responses even in
`int_illuminate__agg_student_responses`. They were created and had conversions
entered, but were never administered.

Every row the model produces today (20,327 across AY2023) is grades 9/10 SAT or
ACT. All four new assessments are 11th grade, so there is no existing 11th-grade
output to diff against.

## Design

### Single path in `int_assessments__college_assessment_practice`

No branching. Sheet membership becomes the sole designation, and the sheet's two
current jobs — designating an assessment and converting its raw score — are
separated so one can happen without the other.

**Drop the `scope` filter.** The `responses` CTE currently ends with
`where a.scope in ('ACT', 'SAT') and a.response_type in ('group', 'overall')`.
Remove the `scope` predicate. This is behavior-preserving: all 12 assessment ids
currently in the sheet are already `scope` `SAT` (8) or `ACT` (4), so no
existing row changes, while the new `Benchmark`-scoped assessments become
eligible.

Preferring this over a `scope` filter means a future Illuminate scope value is
picked up automatically rather than excluded without notice. The four new
assessments are exactly that case — they are scope `Benchmark`, which the
current filter would reject.

**Split the sheet join.** The `responses` CTE joins the sheet with
`inner join ... on a.assessment_id = ssk.assessment_id and a.points between ssk.raw_score_low and ssk.raw_score_high`.
One join currently serves both purposes, so a response survives only if its
`points` value falls inside a conversion row for that assessment. A raw score
outside the sheet's range, or an assessment whose conversions have not been
entered yet, disappears instead of reporting a null scale score. Split into:

- **Designation and metadata** — inner join against
  `select distinct assessment_id, academic_year, test_type, administration_round, subject, grade_level`
  from the sheet.
- **Conversion** — left join against the sheet's conversion rows on
  `assessment_id` plus `points between raw_score_low and raw_score_high`.

**The distinct is load-bearing.** The sheet holds 45-54 conversion rows per
assessment, so an inner join on `assessment_id` alone fans every response row
out roughly 50 times. The current join avoids this only because the
`points between` predicate collapses it to one row. The designation join must
therefore be against a distinct list, and the conversion join must retain the
`points between` predicate.

Carrying the metadata columns on the designation join is safe: verified against
current sheet data, those five attributes are constant within an assessment (12
distinct metadata combinations across 12 distinct assessment ids, zero
assessments with varying metadata), so the distinct yields exactly one row per
assessment and cannot fan out. A uniqueness test on the staging model should
encode this invariant so a future data-entry error fails loudly instead of
silently multiplying response rows.

**Source subject and administration round from the sheet, not Illuminate.**
Illuminate's `subject_area` is null on both `ReadingWriting` assessments and
`administered_at` is null on all four. Three call sites depend on `subject_area`
— the `Mathematics` to `Math` rename, the `course_discipline` `CASE`, and
`count(distinct a.subject_area)` computing `total_subjects_tested`, where a null
silently undercounts because `count(distinct)` skips nulls. A fourth derives
`administration_round` from `administered_at`. All four must read the sheet's
`Subject` and `Administration_Round` columns. Note `scope_round` already reads
`ssk.administration_round` and needs no change.

**Do not add band columns or a `score_basis` discriminator.** Earlier drafts of
this design projected `performance_band_label`, `is_mastery`, and a
`score_basis` column. All three are dropped: the bands are unused, and with
conversions supplied by Foundation there is only one measure, so nothing needs
discriminating. The model's projected column set therefore does not grow.

**Add a third composite branch for the two-section SAT total.** The two existing
trailing `union all` branches are gated on `scope = 'ACT'` with
`total_subjects_tested = 4` (averaging to an ACT composite) and `scope = 'SAT'`
with `total_subjects_tested = 3` (summing to a 400-1600 total). The new
assessments are `Benchmark`-scoped with two subjects, so they match neither.

Because goal thresholds are all full-SAT scale, a section-level score cannot be
compared to any of them, so a total is required. Add a branch gated on the
designated `Benchmark` rows with `response_type = 'overall'` and
`total_subjects_tested = 2`, summing `scale_score` exactly as the 3-subject
branch does.

Two properties make this safe:

- **The `* 10` rescale does not fire.** Both places that apply it are guarded on
  `scope = 'SAT' and subject_area in ('Reading', 'Writing') and grade_level in (9, 10)`.
  The historical sheet stores Reading and Writing on the 10-40 test scale, so
  each is multiplied by 10 and summed with Math to reach 400-1600. The new rows
  are `Benchmark`-scoped, 11th grade, and already section-scaled at 200-800, so
  the guard excludes them on scope alone.
- **A partial administration produces no total.** `total_subjects_tested` is
  `count(distinct subject_area)` over
  `(academic_year, powerschool_student_number, administration_round)`, so a
  student who sits ReadingWriting but not Math counts 1 and the gate rejects
  them. Their section row still reports. This is the intended answer to the
  one-section-only case: no total is better than a 200-800 number sitting next
  to a 1010 threshold, and it matches how the 3- and 4-subject gates already
  behave.

**Stamp `course_discipline` as a constant on the new branch** rather than
selecting it through, to avoid inheriting the duplication defect described in
the findings above.

`practice_scale_score_by_subject` also needs no change. It keeps its inner join
and is already left-joined into the final select, so for an assessment with no
conversion rows it simply contributes nothing and `raw_score` / `scale_score`
return null.

### Designation lives in the existing sheet

The SY26-27 assessment ids go into the existing
`src_google_sheets__kippfwd__act_scale_score_key` spreadsheet. The data team
owns this entry — KIPP Foundation supplies the raw-to-scale conversion tables,
and the data team transcribes them into the sheet.

Conversions for the four SY26-27 assessments arrived from Foundation and are
being entered now, so these rows should carry complete conversion ranges from
the start. The design still must not _require_ them: designation should hold the
moment an assessment id is known, so that a future gap between "assessment
exists" and "conversions received" surfaces as a null scale score rather than a
missing row.

Consequences the implementation must handle:

- **Designation** is the distinct assessment-plus-metadata list described above
  — it must not require non-null `raw_score_low` / `raw_score_high`.
- **Conversion** excludes any conversion-less row naturally, because a `between`
  comparison against `null` bounds never matches. No explicit
  `raw_score_low is not null` guard is required, though one makes the intent
  legible.
- A designation row must carry the assessment's `Subject`, `Grade_Level`, and
  `Administration_Round` regardless of its conversion columns, since those
  fields are what the model reads in place of Illuminate's nulls.

`Administration_Round` in the sheet carries the season. Per the decision below,
BOY is entered as `Fall` and MOY as `Winter`.

`stg_google_sheets__kippfwd__act_scale_score_key` has no `data_tests:` and no
column descriptions, which violates the staging conventions in
`src/dbt/CLAUDE.md`. Adding a uniqueness test is in scope for this work; its key
must tolerate a designation row whose conversion columns are empty.

### Downstream wiring

- `int_tableau__college_assessment_roster_scores` hardcodes
  `'Official' as test_type` on both of its union branches. Add a third branch
  sourcing practice rows and stamping `'Practice'`.
- `stg_google_sheets__kippfwd__expected_assessments` filters
  `where expected_admin_season != 'Not Official'`. Relax it so practice
  administrations reach `_roster`.
- BOY maps to `Fall` and MOY maps to `Winter`, reusing the existing season
  vocabulary rather than introducing new values. `expected_admin_season_order`
  must place them so the existing `growth` CTE's
  `lag(scale_score) over (partition by student_number, expected_scope order by expected_admin_season_order desc)`
  computes BOY-to-MOY change correctly.
- **Goal comparison — placement is an open decision.** Showing practice against
  the existing thresholds is assumed to be required for BOY, so the 400-1600
  total is built either way. Where that total meets the 890 / 1010 / 1200 values
  is not yet decided: outside `_benchmark_calcs` (recommended, keeps
  `rn_highest` ranking official scores only) or inside it (reuses the
  thresholds, but risks the official college-ready metric). Nothing in the
  `_practice` model work depends on this, so it can be settled after the total
  exists.

## Deliverables

1. `int_assessments__college_assessment_practice`: drop the `scope` filter,
   split the sheet join into designation-plus-metadata and conversion, and
   source subject and administration round from the sheet. No new projected
   columns. Plus properties YAML updates.
1. Third composite `union all` branch in the same model, summing the two section
   scale scores into a 400-1600 total for `Benchmark` rows with
   `total_subjects_tested = 2`, with `course_discipline` stamped constant.
1. Downstream wiring in `int_tableau__college_assessment_roster_scores` and
   `stg_google_sheets__kippfwd__expected_assessments`. Threshold comparison for
   practice totals is pending the placement decision above.
1. Uniqueness test and column descriptions on
   `stg_google_sheets__kippfwd__act_scale_score_key`.
1. Reference doc at `docs/models/carat-dashboard-data-model.md`, added to the
   `Models` section of the mkdocs nav, following the
   `gradebook-audit-data-model.md` precedent. It must record: the seven live
   exposure models and what each is actually scoped to, the three parallel goal
   mechanisms, the per-model ACT and academic-year filter differences, the three
   disabled models and why, and the designation/conversion split.
1. Skill at `.claude/skills/carat-dashboard/SKILL.md` with procedures for adding
   a practice assessment for a new year, changing a goal threshold (naming all
   three mechanisms), and debugging a score that is not appearing.
1. Low-priority fix in `rpt_tableau__college_assessment_dashboard_current`:
   replace the four hardcoded `academic_year = 2025` filters with
   `var("current_academic_year")`.

## Three parallel goal mechanisms

Recorded here because the reference doc must document them and because the
deferred goals work will have to unify them.

| Mechanism                                          | Shape                                                                      | Consumed by                                                |
| -------------------------------------------------- | -------------------------------------------------------------------------- | ---------------------------------------------------------- |
| `stg_google_sheets__kippfwd__goals`                | Metric-label based, granularity via null region / schoolid / grade         | `_current`, `_over_time`                                   |
| Hardcoded `CASE` in `_benchmark_calcs`             | 15 `benchmark_group` strings and thresholds in SQL                         | `_benchmark_calcs`                                         |
| `stg_google_sheets__kippfwd__expected_assessments` | Season and administration based, surrogate `expected_unique_test_admin_id` | `_roster`, `int_tableau__college_assessment_roster_scores` |

The same thresholds appear in two of them under different naming — 890 and 1010
exist both as goals-sheet metric labels and as `_benchmark_calcs` literals,
while `EA/ED-Ready` (1200) exists only in the hardcoded `CASE`. The hardcoded
set cannot be changed without a pull request, which is the "easier to update"
problem this project eventually has to solve.

## Academic-year filter map

Only `_current` carries hardcoded years. Recorded so the deprioritized rollover
is not mistaken for a network-wide change.

| Model                     | Year handling                                                                                                                |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `_current`                | Four hardcoded `academic_year = 2025`; `Attempts` branch uses the var                                                        |
| `_roster`                 | `var("current_academic_year")` and `graduation_year >= var + 1`                                                              |
| `_over_time`              | No year filter — lifetime by design; includes ACT                                                                            |
| `_scores`                 | No year filter; excludes only `act_english` / `act_science`                                                                  |
| `_benchmark_calcs`        | No year filter; excludes ACT entirely                                                                                        |
| `_de`                     | Dual enrollment from PowerSchool stored grades; unrelated                                                                    |
| `ap_assessment_dashboard` | No year filter; anchored on `date(academic_year + 1, 05, 01)` falling inside the enrollment window. Not touched by this work |

## Verification

Scores will not exist at implementation time, so end-to-end validation is not
possible. Verify in these layers instead:

1. **Historical parity.** `int_assessments__college_assessment_practice` must
   return the same rows for AY2023 before and after the change — 20,327 rows
   across 4 ACT and 6 SAT assessments. Compare `count(*)` plus
   `count(distinct format("%T|%T", ...))` on the key columns against prod. Any
   row-count increase means the designation join fanned out and the distinct is
   wrong. Because neither pre-existing defect is being fixed here, this stays a
   clean behavior-preserving check with no restated baseline.
1. **The new total, arithmetically.** With no SY26-27 responses, exercise the
   two-section sum against a fabricated dev fixture: two designated `Benchmark`
   assessments, one student with both sections, one with only ReadingWriting.
   Confirm the first yields exactly one total row in 400-1600 equal to the sum
   of its two sections, and the second yields none. Confirm the `* 10` rescale
   did not fire on either.
1. **New-assessment shape with no data.** With the four ids designated and no
   responses, they contribute zero rows and the model still builds, tests pass,
   and the contract holds.
1. **Designation without conversion.** In a dev copy, add a designation row with
   empty `raw_score_low` / `raw_score_high` for an existing AY2023 assessment
   and confirm its responses survive with `scale_score is null`, rather than
   being dropped. This is the anti-silence property the split join exists to
   provide.
1. **A loud failure where there is currently none.** Add a test that fails when
   a designated assessment has responses in `int_assessments__response_rollup`
   but produces no rows in `int_assessments__college_assessment_practice`. This
   is what will confirm SY26-27 scores landed correctly, since nothing else can
   be checked before they arrive.

## Out of scope

Deferred to a follow-up spec once KIPP Forward's updated strategy and goals
documents are available:

- Unifying the three goal mechanisms and moving the hardcoded `_benchmark_calcs`
  thresholds into a maintainable source.
- Whether `ReadingWriting` and `Math` rows combine into a 400-1600 SAT total,
  and the rule for a student who sits one section but not the other.
- Goal thresholds for practice assessments.

Also out of scope:

- **The two pre-existing defects**, both documented in the findings above and
  both deliberately left alone so the parity gate stays a clean
  behavior-preserving check: `course_discipline` reading `NA` on all 7,397 math
  rows, and the duplicated composite rows. Both should be filed as their own
  issue.
- **Where practice totals meet the goal thresholds.** The total is built in this
  work; the placement decision is deferred.
- **Illuminate performance bands.** `is_mastery`, `performance_band_label`, and
  `performance_band_label_number` are available from
  `int_assessments__response_rollup` for every assessment including the four new
  ones, and the model already discards them. They stay discarded — KIPP Forward
  does not use Illuminate mastery levels for practice SAT reporting, so there is
  no reason to widen the model to carry them. A `score_basis` discriminator
  column proposed in an earlier draft is dropped along with them.
- Re-enabling `rpt_tableau__college_assessment_dashboard`,
  `rpt_tableau__college_assessment_dashboard_historic`, or
  `rpt_tableau__college_assessment_qc_report`. They stay `enabled: false`.
  Historical ACT already displays on the live `_over_time` model.
- Collapsing `_current`'s four near-identical `Benchmark` union branches into a
  Jinja loop. The branches differ only in the `granularity_level` literal, one
  join predicate, and the null guards on `expected_region` / `expected_schoolid`
  / `expected_grade_level`, so the consolidation would remove roughly 580 of the
  model's 907 lines. It is deferred because the deferred goals work rewrites
  those same branches, and doing both at once means editing `_current` twice.

## Prerequisites

- The data team enters the four assessment ids in the `act_scale_score_key`
  spreadsheet, with `Administration_Round` set to `Fall` for BOY and `Winter`
  for MOY. Foundation's scale-score conversions are in hand and are being
  entered alongside them, so these rows should carry complete conversion ranges
  rather than blanks. This is owned by us, not a wait on another team.
- Illuminate administration windows on the four assessments are null. Setting
  them is not required by this design, but without them `response_rollup`'s
  `term_administered` will not resolve for practice rows.
