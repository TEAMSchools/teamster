# CARAT 2026 rebuild — measured changes

What the summer 2026 CARAT rebuild changed, measured against production at the
time. The reference doc (`docs/models/carat-dashboard-data-model.md`) explains
how the models work now; this file holds the before/after figures the skill
cites when someone asks why a number moved. Section names here are what the _Why
did this number change_ table in [SKILL.md](../SKILL.md) points at.

## Practice hub: changes when it replaced the AY2023-era model

Verified by full comparison against production. Section rows are **identical** —
join key unique on both sides at 18,224 rows, zero differences in `scale_score`,
`raw_score`, `points`, `percent_correct`, dates, or titles. Composite rows
change in three ways:

| Change                                           | Rows |
| ------------------------------------------------ | ---- |
| Duplicate composites collapse                    | -851 |
| Incomplete sittings gain a row with a null total | +200 |
| Four students lose an invalid total              | -4   |

**Duplicates collapse.** Production emitted one composite row per distinct
`course_discipline` per student-round, because it used `select distinct` over
columns that vary within the partition. 2,103 rows became 1,252. Lossless: every
duplicated group carried an identical scale score.

**Incomplete sittings become visible.** Production's `where … = 3` dropped a
student who sat 2 of 3 sections, making an incomplete attempt indistinguishable
from no attempt. Those rows now exist with a null `scale_score` and the two
count columns showing why. 162 SAT and 46 ACT student-rounds.

**Four students lose a total, and production's numbers for them were wrong.**
Four students each sat two sections of the grade-10 SAT form and one of the
grade-9 form in the same round. Production pooled all three and reported a
3-of-3 total — 620, 550, 520 and 600 respectively — summing sections from two
different test forms on two different scales. Splitting by grade means neither
half reaches 3 of 3, so both totals are null. These four are the only students
whose existing scores change, and the change is a correction.

`course_discipline` is also corrected on 8,426 section rows: Math moves from
`NA` to `MATH` (7,397 rows) and Science from `NA` to `SCI` (1,029). Production's
`CASE` tested the raw `Mathematics` value while the rename to `Math` happened in
a sibling column of the same `SELECT`, and BigQuery has no lateral column
aliases. The derivation now lives in the scaffold sheet instead.

Schema: `total_subjects_tested` is replaced by `actual_total_subjects_tested`
and `expected_total_subjects_tested`. Added: `grade_level`, `subject`,
`aligned_subject_area`, `score_type`.

## Roster scores: what the repointing changed

Official SAT, PSAT10 and PSAT NMSQT are unchanged — same rows, same students,
zero score disagreements against production. The other two groups changed, and
both were production defects:

| group                         | before | after | why                                            |
| ----------------------------- | -----: | ----: | ---------------------------------------------- |
| Official SAT / PSAT10 / NMSQT |  4,980 | 4,980 | exact parity                                   |
| Official PSAT 8/9             |  5,562 | 2,781 | every score was counted into both seasons      |
| Practice PSAT 8/9 and PSAT10  |  4,107 |     0 | official scores carrying a practice label      |
| Practice SAT                  |      0 |    30 | real practice scores that never had a join key |

The PSAT 8/9 double-count came from the missing month binding: the tab carries
grade 9 PSAT 8/9 in two seasons, Fall (October) and Spring (March), and every
score matched both. All 927 students sat it in October, so the Spring rows were
entirely fabricated. The March administration is real but has not happened yet —
it is scheduled for 3 March 2027 — so that scaffold row is correctly empty until
then.

The practice rows were the same failure one level up: with `test_type` unbound,
a practice scaffold row matched any official score sharing its score type. Both
PSAT 8/9 and PSAT10 practice populations were identical to their official
counterparts — same students, same score ranges — because they _were_ the
official scores.

!!! warning "Practice figures on the roster dashboard drop sharply"

    Practice students fall from 899 to 10 and practice rows from 4,107 to 30.
    Every row removed is fabricated and the 30 that remain are real, but anyone
    watching the dashboard will see it as a collapse. Tell KIPP Forward before
    they find it.

## Why participation attempt counts change

`int_students__college_assessment_participation_roster` reports different
numbers after this work, and so does anything reading its `*_count_lifetime`
columns — `_dashboard_roster` and `rpt_gsheets__college_assessments_wide`.
`_over_time` and `_current` used to read them and now derive their own counts
from `attempt_lifetime` on the hub instead. Measured student by student against
production across all 4,554 students and all five lifetime counts:

| Group                                       | Students  |
| ------------------------------------------- | --------- |
| identical on all five lifetime counts       | **4,453** |
| SAT lower                                   | 86        |
| SAT higher                                  | 8         |
| ACT higher (one student also in SAT higher) | 8         |
| any PSAT 8/9, PSAT10 or NMSQT difference    | **0**     |

The student set is unchanged — nobody present in one and absent from the other.
PSAT counts do not move at all. Two causes, both intended.

### 86 students lose one SAT attempt — the duplicate correction

These are the double-entered Salesforce records described under _Known issue —
duplicate kippadb test records_ in the reference doc. Counting distinct test
dates instead of rows credits one sitting once. Almost all are Camden class of
2027 on the April 2026 school-day SAT.

This is the change most likely to be questioned, because that cohort's SAT
`2+ Attempts` rate is measured against an 0.95 goal and a student sitting
exactly on the one-versus-two boundary flips from meeting it to not. The rate
falls because double-counting stopped, not because participation dropped.

### 16 students gain an attempt — counts are no longer scoped to enrollment years

`attempt_lifetime` is computed on the hub before any enrollment filter, so a
sitting in a year the student had no high school enrollment record counts toward
their lifetime total. The old chain counted only rows surviving that join, so it
dropped them.

This is deliberate and matches how attempts are treated elsewhere — a test sat
outside our schools still counts. The roster's **population** is still scoped to
enrolled high school students, because the Tableau views require it; only the
counts span a student's whole history.

### 13 students gain a row, with no count change

Row count goes 7,294 to 7,307 on the Official side. Those 13 are grade
repeaters: one student holding two academic years at the same grade level, which
the old grain merged and `academic_year` now separates. All 26 rows carry
attempts, none is empty, and no lifetime count differs. They never reach
consumers, because `rn_lifetime = 1` still yields one row per student per test
type.

A further 378 rows are Practice, which production had no concept of.

### If you are reconciling and the numbers do not match this table

The counting fix and a Salesforce cleanup of the duplicate records address the
same rows from opposite ends. Whichever lands first absorbs the correction and
the other becomes a no-op for these counts, so a comparison run after a cleanup
shows a smaller delta than the table above — not because the fix did nothing.

## Why the benchmark dashboard's totals change

`rpt_tableau__college_assessment_dashboard_benchmark_calcs` reports different
numbers after this work. **No student's score changed** — verified by full
comparison of the rebuilt view against production, zero differences in
`max_score` across all 8,262 shared keys. What changed is the row set and one
threshold.

### One student-facing change: 20 students move to Met

Exactly one threshold moved:

| Scope    | Subject  | Tier          | Production | Now |
| -------- | -------- | ------------- | ---------- | --- |
| PSAT 8/9 | Combined | HS Grad-Ready | 800        | 790 |

That is the intended correction — the value now comes from the scaffold sheet
instead of a hardcoded `CASE`. **20 students move from `Not Met` to `Met`** as a
result. Lowering a threshold cannot move anyone the other way, and `No Data` is
unaffected because it depends on a null score rather than on the threshold.

Anyone reconciling a percent-met figure against a pre-merge screenshot should
expect PSAT 8/9 HS Grad-Ready to rise slightly for that reason alone.

### The row set changes shape, so old and new keys mostly do not line up

Production emits 100,590 rows; this version emits 241,416, over the same 6,706
students. Only about 8,262 keys are directly comparable. Three reasons:

- **`EA/ED-Ready` is retired.** Its three thresholds (PSAT 8/9 and PSAT10/NMSQT
  at 1100, SAT at 1200) are gone. SAT 1200 existed nowhere else.
- **Section rows carry a readiness tier now.** Production put the subject name
  in `benchmark_name` for section rows (`EBRW`, `Math`) and a tier only on
  `Combined`. Every subject area now carries both `HS Grad-Ready` and
  `College-Ready`, which is most of the row-count growth.
- **`Practice` rows exist.** Production had `Official` plus a set of rows with a
  null `test_type`; both are replaced by explicit `Official` and `Practice`.

### Practice benchmarks resolve against practice scores only

The view joins `expected_test_type` to the hub's `test_type`, and the hub's
benchmark rank partitions on `test_type` as well, so a practice result can never
satisfy an official benchmark or displace an official best. That is what made it
safe to let practice reach this view at all — the risk flagged during design was
precisely that `rn_highest = 1` would let a practice score outrank an official
one.

### Not changed here: the 27 suppressed scores

This view reads `benchmark_aligned_scope_max_score`, which retains its
`rn_highest = 1` filter, so 27 students who hold eligible scores still read
`No Data` in the benchmark view. That matches production deliberately.

`rpt_tableau__college_assessment_dashboard_over_time` **no longer suppresses
them** — see _Why the over-time dashboard's numbers change_ below. The two views
therefore disagree on those 27 students until the benchmark view is repointed,
which is expected rather than drift.

## Why the over-time dashboard's numbers change

`rpt_tableau__college_assessment_dashboard_over_time` reports different numbers
after this work, from five separate causes. They are listed separately because
they land on different grad years, and reconciling against a pre-merge
screenshot means knowing which one you are looking at.

### Row count

Production emits 292,656 rows — 6,968 students times 42 goal rows. This version
emits 556,406:

|                                                           | rows        |
| --------------------------------------------------------- | ----------- |
| Official, 40 goal combinations                            | 278,040     |
| plus `strategy_case` emitting two rows for one score type | 326         |
| **Official total**                                        | **278,366** |
| Practice, 40 goal combinations, no fan-out                | 278,040     |

Production's 42 is 40 distinct combinations plus 2 duplicates — SAT HS
Grad-Ready and College-Ready are stated per grade, and the view projects neither
grade nor cohort, so both rows arrive per student differing only in `pct_goal`.
Tableau resolves the pair with `MIN()`. The sheet's over-time goal columns
replace that, which is why the count drops to 40.

All 40 Official goal combinations are structurally identical to production —
compared across `expected_aligned_subject_area`, `expected_aligned_subject`,
`expected_metric_name`, `min_score` and `pct_goal`, with zero naming or
alignment mismatches. So the `expected_aligned_subject_area` correction changed
no values.

### Attempt counts fall for 87 students

174 rows, being 87 students across the two SAT attempt metrics, all lower and
none higher. Two causes, both covered in _Why participation attempt counts
change_: the duplicate Salesforce records, and counting distinct test dates
rather than rows.

### 27 students gain a score production suppresses

Production joins scores with `and s.rn_highest = 1`, which discards a score
whose rank was spent on a sibling row later dropped for a missing test date —
the known issue documented in the next section. This version reads the hub
through a `max(scale_score)` CTE with no rank filter, so those scores return.
**This was a side effect of the refactor rather than a planned change, and it is
kept deliberately**: re-adding the filter would mean suppressing known-good
scores to preserve a defect.

Nothing is lost in the other direction — zero rows go from scored to null. The
effect is confined to three historical grad years:

| Grad year | Students restored                                 | Effect                                    |
| --------- | ------------------------------------------------- | ----------------------------------------- |
| 2015      | 13 benchmark, 16 SAT 1-Attempt, 6 SAT 2+          | +8.1pp on HS Grad-Ready and College-Ready |
| 2014      | 3 College-Ready, 2 HS Grad-Ready, 3 SAT 1-Attempt | +1.3 to +1.9pp                            |
| 2022      | 2 benchmark, 7 ACT 1-Attempt, 7 ACT 2+            | +0.3 to +1.3pp                            |

**No live cohort moves from this cause.** Measured with a causal decomposition
per grad year: on all three, the students who move have a score that appeared,
and none of them have a threshold that changed.

One thing to expect when reading the flags: a single restored score flips the
flag on more rows than there are students, because
`met_min_score_int_overall_aligned_scope_subject` is a max over a partition that
spans score types. One restored SAT score flips both the `sat_total_score` and
`act_composite` rows inside the same ACT/SAT-and-Total partition, so 13 students
show as 26 moved rows.

### PSAT 8/9 HS Grad-Ready rises for 2028 and 2029

The threshold moved 800 to 790, so 10 students in each of grad years 2028 and
2029 cross it — +1.7pp and +1.5pp respectively. Decomposed the same way: every
one of those 20 has an unchanged score and a changed threshold, so this is the
threshold correction and not the restored scores above. These are the only live
cohorts that move at all.

### Practice doubles the row count

40 Practice goal combinations against 40 Official, with no score-side fan-out.
This is the point of the work rather than a side effect.

## Why the current dashboard's numbers change

`rpt_tableau__college_assessment_dashboard_current` was five near-identical
union branches emitting one row per student per granularity level. It is now one
branch emitting one row per student per goal, with the workbook aggregating its
school, regional and network views from those rows. A `ktaf` literal carries the
network level alongside `state`, `region` and `school`.

That collapse is only possible because goals stopped varying by school and
region. **Every level now shows the same goal line** for a given grade and
metric, where production showed 9 distinct school goals and 7 regional ones.
That is the most visible change in this work and it is a KIPP Forward decision,
not a modelling one.

### The row shape is reproduced exactly for Official

| Block                            | Production | Now    |
| -------------------------------- | ---------- | ------ |
| Official sections, 8 score types | 32,224     | 32,224 |
| Official totals, 4 score types   | 5,106      | 5,106  |
| Practice sections                | none       | 32,224 |
| Practice totals                  | none       | 4,028  |

Production's `Region/Grade Level` and `School/Grade Level` blocks were
row-for-row identical to `Org/Grade Level`, differing only in the label and
which `pct_goal` attached, so collapsing them loses nothing.

### Only a total-level Benchmark is grade-specific

Attempts and section thresholds apply to every student regardless of grade — a
grade 9 student has sat the SAT zero times, which is a reportable answer, and
section thresholds are reference bars that production carried at no grade at
all. A total-level Benchmark is reported only where a goal was set for that
grade.

Getting this wrong is easy in both directions. Requiring a grade match on
Attempts drops them to a quarter of their rows. Letting null-grade rows apply to
everyone pulls in total-level thresholds that merely lack a goal — Practice
`psatnmsqt_total` has a scaffold threshold and no stated goal, and it inflated
the Practice totals by 4,028 rows before the rule was narrowed.

### The attempts denominator is test takers, and a zero is not a null

An attempts score reads **0** where the student holds any result of that test
type but never sat this particular test, and **null** where they hold no result
at all. Production reached the same population by reading the participation
roster, whose grain is enrollment intersected with results; this version derives
it from the hub with a student-level flag.

This is the single most dangerous thing in the model to get wrong. Every
attempts metric shares one denominator — 1,319 of 2,090 enrolled students — and
treating a non-tester as 0 rather than null moves it to 2,090, **roughly halving
every reported percentage**. SAT 1 Attempt reads 31.8% against 20.2%. Nothing
errors and no row count changes; only the denominator moves.

### Board metrics became one column

The four `met_min_board_*` flags and the sixteen threshold columns behind them
are replaced by `benchmark_tier`, a three-way band of College-Ready, HS-Grad
Ready, or No Benchmark Met. Every board threshold was already a scaffold value:

| Board metric      | Board `min_score` | Scaffold column           |
| ----------------- | ----------------- | ------------------------- |
| sat_combined 890  | 890               | `hs_grad_ready_min_score` |
| sat_combined 1010 | 1010              | `college_ready_min_score` |
| sat_ebrw 450      | 450               | `hs_grad_ready_min_score` |
| sat_math 440      | 440               | `hs_grad_ready_min_score` |

So `Board` was a duplicate encoding of the two tiers, and the jinja loop that
pivoted it is gone. The board goal percentages were genuinely distinct — 0.25
and 0.28 for the 890 tier against the Benchmark goals' 0.45 and 0.35 — because
that view reports over test takers rather than all enrolled students. Those
separate targets do not survive: one goal now applies everywhere, so the NJ Grad
Ready goal line moves to the sheet's HS Grad-Ready value.

### Everything else that moves

- **The academic year.** Production's stored view has `2026` on the Attempts
  branch, from the var, and `2025` hardcoded on all four Benchmark branches — so
  the live report serves attempts a year ahead of benchmarks. Both now read the
  var. This is the largest mover and it is the rollover this work exists for.
- **86 students' SAT attempt counts fall**, from the duplicate Salesforce
  records.
- **2 students gain attempt values** across all 8 metrics, because counts are no
  longer scoped to enrolled years.
- **PSAT 8/9 HS Grad-Ready moves 800 to 790**, flipping 10 rows.
- **Every total row's `pct_goal` changes**, the sheet having been restated.
- **`expected_metric_label` is now populated on Benchmark rows** where
  production read null. Additive, with no measure impact.

Validated by pinning both sides to the same academic year, since production's
mixed years make a direct comparison meaningless — Benchmark rows against AY2025
and Attempts rows against AY2026, matching what production's own stored view
compiles to.

|                                                      | Benchmark | Attempts |
| ---------------------------------------------------- | --------- | -------- |
| Rows matched                                         | 37,330    | 16,720   |
| Production rows not covered                          | 0         | 152      |
| Rows only in this version                            | 36,252    | 16,720   |
| `score` differences                                  | **0**     | 188      |
| `met` / `alt_met` differences                        | 10 / 10   | 4 / 6    |
| `expected_scope`, both subject columns, `score_type` | 0         | 0        |

Every row only in this version is Practice. The 152 production rows not covered
are 19 students absent from the developer copy of
`int_extracts__student_enrollments` and present in production's — a stale defer
copy rather than a dropped population, confirmed by checking all 19 against
both.

`expected_metric_label` differs on every Benchmark row and none of the Attempts
rows, which is the additive change noted above rather than a discrepancy.
