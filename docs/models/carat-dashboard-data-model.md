# CARAT Dashboard Data Model

Reference for the College Admission Readiness Assessments Tracker (CARAT)
Tableau workbook and the dbt models behind it.

## What is CARAT?

CARAT is the KIPP Forward dashboard for college-entrance assessment results —
SAT, PSAT 8/9, PSAT 10, PSAT NMSQT, and historical ACT. It reports scores,
participation, benchmark attainment, and progress against goals, for current
high school students and recent cohorts.

## Models behind the workbook

The `college_admission_readiness_assessments_tracker_carat` exposure declares
seven models. The AP model is documented separately and is out of scope here.

| Model                                                       | Purpose                                    | Documented   |
| ----------------------------------------------------------- | ------------------------------------------ | ------------ |
| `rpt_tableau__college_assessment_dashboard_scores`          | Score-level detail for average-score views | below        |
| `rpt_tableau__college_assessment_dashboard_current`         | Current-year goal attainment               | pending      |
| `rpt_tableau__college_assessment_dashboard_over_time`       | Multi-year goal trend                      | pending      |
| `rpt_tableau__college_assessment_dashboard_roster`          | Student roster with participation counts   | pending      |
| `rpt_tableau__college_assessment_dashboard_benchmark_calcs` | Benchmark thresholds and attainment        | pending      |
| `rpt_tableau__college_assessment_dashboard_de`              | Dual enrollment                            | pending      |
| `rpt_tableau__ap_assessment_dashboard`                      | AP results                                 | out of scope |

Three further models exist in the repo but are `enabled: false` and are not part
of the workbook — `rpt_tableau__college_assessment_dashboard`,
`_dashboard_historic`, and `_qc_report`.

### Two score pipelines

Every question about CARAT numbers starts with which pipeline is involved,
because the two never mix inside a single model:

| Pipeline | Hub model                                      | `test_type` | Origin                                          |
| -------- | ---------------------------------------------- | ----------- | ----------------------------------------------- |
| Official | `int_assessments__college_assessment`          | `Official`  | kippadb and College Board                       |
| Practice | `int_assessments__college_assessment_practice` | `Practice`  | Illuminate plus the `act_scale_score_key` sheet |

## `rpt_tableau__college_assessment_dashboard_scores`

### What it powers

One view, on the workbook's landing page — average scores over time by
graduation-year cohort.

- Rows: `test_type`, then `graduation_year`
- Columns: `scope` — PSAT 8/9, PSAT 10, PSAT NMSQT, SAT, ACT
- Measure: average of the selected score column
- Filters: Region, School, Aligned Subject Area, Grad Year, Score Category

Score Category selects between the two measure columns, `scale_score` and
`max_scale_score`. Aligned Subject Area selects `Total` or a section.

### Lineage

```text
int_assessments__college_assessment          (official hub — SAT/PSAT/ACT)
int_extracts__student_enrollments            (region, school, grad year, cohort)
        └─ rpt_tableau__college_assessment_dashboard_scores
```

The model is a single `select` with one join and no CTEs — the simplest of the
six. It adds no calculation; all aggregation happens in Tableau.

### Grain

One row per student per score record. Approximately 29,000 rows across roughly
4,600 students, spanning graduation years 2011 through 2029.

### Behavior worth knowing

**Only official scores can ever appear here.** The model reads the official hub
alone, so `test_type` has exactly one value, `Official`. The workbook still
shows `test_type` as a row header, which suggests it was built anticipating
practice rows — but no practice score can reach this view without adding a
second union branch reading `int_assessments__college_assessment_practice`.

**Region and school are the student's current values, not the values at test
time.** The enrollment join matches on `student_number` only, with no
`academic_year` predicate, against the enrollment row where `rn_year = 1`. So
every score a student has ever earned is attributed to whichever region and
school they are enrolled in now. For cohort reporting this is usually the intent
— a student's results follow them — but it means a student who transferred
regions moves their entire score history with them, and regional averages shift
retroactively when students transfer. The enrollment side contributes exactly
one row per student, so the join causes no fan-out.

**The score-type filter is a denylist, not an allowlist.** Six sub-test score
types are excluded by name — `act_english`, `act_science`, `psat10_math_test`,
`psat10_reading`, `sat_math_test_score`, `sat_reading_test_score`. Any score
type added upstream in future is therefore included automatically. That makes
the view resilient to new assessments but means an unexpected score type appears
in the scope columns without a code change.

**This model is deduplicated, and the duplicates come from Salesforce.** See
_Known issue — duplicate kippadb test records_ below. The model applies
`dbt_utils.deduplicate` on `student_number`, `score_type`, `test_date`, and
`scale_score`, which is lossless because those four columns functionally
determine every other projected column. A uniqueness test on that key guards the
deduplication, so new non-identical duplicates upstream fail loudly instead of
shifting a reported average.

**A small number of rows carry no graduation year.** Fewer than ten. They fall
out of any grad-year-grouped view silently rather than appearing in an unknown
bucket.

## `stg_google_sheets__kippfwd__scaffold`

The assessment vocabulary — every valid combination of academic year, test type,
scope, and score type, with its subject alignments and cut scores. 29 rows: 16
Official, 13 Practice (Practice has no ACT).

Grain is (`academic_year`, `expected_test_type`, `expected_scope`,
`expected_score_type`), enforced by a composite uniqueness test.

### Why it exists

Four models were each hand-deriving the same mappings from scope and score type,
because they were never stored as data:

| Model                                                       | Derived                                                                               |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `stg_google_sheets__kippfwd__goals`                         | `expected_aligned_scope`, `expected_aligned_subject_area`, `expected_aligned_subject` |
| `stg_google_sheets__kippfwd__expected_assessments`          | `expected_grouping`, `expected_score_category`                                        |
| `int_assessments__college_assessment`                       | `aligned_subject_area`, `aligned_subject`                                             |
| `rpt_tableau__college_assessment_dashboard_benchmark_calcs` | 15 hardcoded thresholds, a 15-string `unnest`, three `regexp_extract` parses          |

`_benchmark_calcs` is the clearest case: it concatenates `benchmark_group`
strings, then immediately re-parses them with three regexes to recover the
scope, subject, and tier it just encoded. This model stores those as columns, so
the CASE, the list, and all three regexes go away together. It also closes a gap
— `_benchmark_calcs` carries only the College-Ready threshold for its six
subject-level groups, while this carries both tiers for all of them.

Separating it from the goals sheet is also what makes the empty-goal-rows
problem solvable. See _Goal type — Attempts_ below: the goals sheet is currently
doubling as this list, which is why rows with no target cannot be deleted.

### The alignment columns are not interchangeable

Three columns collapse the same fields differently, and picking the wrong one
silently changes what a view reports:

| Column                          | ACT Reading vs EBRW | Growth vs Total |
| ------------------------------- | ------------------- | --------------- |
| `expected_subject_area`         | separate            | merged          |
| `expected_aligned_subject_area` | **merged**          | merged          |
| `expected_grouping`             | separate            | **separate**    |

### Gotchas

**`expected_grade_level` is a string holding a comma-separated list.** One row
covers `11,12` where SAT and ACT share a target across both grades. Split with
`cross join unnest(split(expected_grade_level, ','))` — the same pattern
`int_collegeboard__ap_unpivot` uses for AP course codes — and use
`left join unnest` if the column can ever be blank, because `cross join` to an
empty array deletes the row silently.

**The source schema is pinned explicitly, and has to be.** Autodetect samples
the single-grade rows first, types `expected_grade_level` as `int64`, and then
fails to parse `11,12`. The `columns:` block in `sources-external.yml` forces
`string`.

**`stage_external_sources` skips a table that already exists.** A schema change
needs `--vars "ext_full_refresh: true"` or the old autodetected schema persists
and the model fails its contract check.

**The named range is `src_google_sheets__kippfwd__scaffold`** — two underscores
before `scaffold`, where every sibling range uses one.

**`a1_attempt_min_score` / `a2_plus_attempts_min_score`** lead with `a` because
a column name cannot start with a digit.

## Goal type — Attempts

Attempt goals answer "what share of students sat this test at least once, and at
least twice." They are the simplest of the goal types and the clearest example
of a structural problem that affects all of them, so they are documented first.

### The goals sheet does two jobs, and that is why empty rows cannot be deleted

`stg_google_sheets__kippfwd__goals` simultaneously declares **which score types
exist** and **which score types have targets**. The scaffold role is not
documented anywhere in the sheet — it is a side effect of how
`rpt_tableau__college_assessment_dashboard_current` reads it:

```sql
from int_assessments__college_assessment as s
inner join stg_google_sheets__kippfwd__goals as g
    on s.score_type = g.expected_score_type
    and g.expected_goal_type != 'Board'
```

The join is `inner` and keyed on `score_type` alone, so a score type with no
goals row disappears from the dashboard entirely.

The consequence is counterintuitive: **rows with no goal value are
load-bearing.** Deleting rows where `pct_goal is null` would drop 11 of 15 score
types from `_current` — every section-level type (`sat_ebrw`, `sat_math`,
`psat10_math_section`, `psat89_ebrw`, …) and all of ACT, because their Benchmark
rows carry null `pct_goal` too. Only the four `*_total` types would survive.

Until the two roles are separated — scaffold from
`stg_google_sheets__kippfwd__expected_assessments` or from
`int_assessments__college_assessment` directly, targets from goals — empty rows
stay, and `pct_goal is not null` is the de facto "this goal is tracked" flag.

### What is tracked

A populated `pct_goal` means the goal is actually tracked; a null means the row
exists only as scaffold. Reading the sheet that way:

| Year | Tracked for attempts                                                         |
| ---- | ---------------------------------------------------------------------------- |
| 2025 | SAT only — 1 attempt 95%, 2+ attempts 80%                                    |
| 2026 | SAT, PSAT 8/9, PSAT 10, PSAT NMSQT at 95% for 1 attempt; SAT also 80% for 2+ |

The PSATs have no `2+ Attempts` target because they are administered once a
year. PSAT NMSQT is counted as PSAT 10 where needed, which is also why
`_benchmark_calcs` folds them into a single `PSAT10/NMSQT` threshold group.

### Grain

Once goals stop varying by region, school, and grade level — the current
direction, and already true of every attempts row today (all ten have `region`,
`schoolid`, `grade_level`, and `cohort` null) — an attempts goal is uniquely
identified by:

```text
(academic_year, expected_test_type, expected_scope, goal_category)
```

`goal_category` is the attempt tier, `1 Attempt` or `2+ Attempts`. No pivot is
needed at this grain, which removes the 18-branch `CASE` in the staging model
that maps `'PSAT10 1 Attempt'` to `psat10_1_attempt`, along with
`expected_metric_name` and `expected_metric_label`.

### The 12 columns in the participation roster have no consumer

`int_students__college_assessment_participation_roster` unpivots and re-pivots
the attempts goals into 12 columns (`sat_1_attempt_min_score`,
`psat89_2_plus_attempts_min_score`, and so on) via `cross join attempt_goals`.
All four consumers of the roster read only the `*_count_lifetime` columns and
`rn_lifetime` — none reads a goal column.

The `cross join` is safe today only because the pivot collapses all ten goal
rows into exactly one. **It stops being safe as soon as the goals source carries
`academic_year`**, which yields one row per year, or `expected_test_type`, which
adds a `Practice` row — either fans the roster 2-3× silently.

So the columns should be dropped rather than ported. A consumer that needs an
attempts goal joins the long-format goals table on `academic_year` and
`expected_scope`. The roster counts are already per scope (`psat89_count`,
`psat10_count`, `sat_count`, …), so the shapes line up — but the roster
currently discards `academic_year` in its `yearly_tests` pivot and would have to
carry it through to join on.

### The attempt count itself is wrong, independent of the goal

`rpt_tableau__college_assessment_dashboard_over_time` computes `alt_attempts`
with `count(*)`, so the duplicated Salesforce records described under _Known
issue — duplicate kippadb test records_ count as separate sittings. **Four
students currently read as meeting the "2+ Attempts" goal on the strength of a
duplicate record.** `count(distinct test_date)` fixes it. Reformatting the goals
sheet does not — this is a measure defect, not a goal-definition defect.

### `min_score` carries two different meanings

On an attempts row `min_score` is an attempt count (1 or 2). On a Benchmark row
it is a scale score (890, 1010). A threshold comparison therefore cannot be
written generically against the column, and for attempts it duplicates what
`goal_category` already says. Worth resolving before Benchmark rows land in a
reformatted sheet — either drop it from attempts rows or rename it to something
type-neutral and document it per `goal_type`.

## Goal type — Benchmark

Benchmark goals answer "what share of students scored at or above a threshold."

### Which models read them

| Model                                                       | How                                                                   | In workbook |
| ----------------------------------------------------------- | --------------------------------------------------------------------- | ----------- |
| `rpt_tableau__college_assessment_dashboard_current`         | inner join on `score_type`, `goal_type != 'Board'`, all granularities | yes         |
| `rpt_tableau__college_assessment_dashboard_over_time`       | `goal_type != 'Board'` and `region is null and schoolid is null`      | yes         |
| `rpt_gsheets__college_assessments_long`                     | `goal_type = 'Benchmark'`, network only, `avg(min_score)`             | no          |
| `rpt_tableau__college_assessment_dashboard_benchmark_calcs` | **none** — thresholds hardcoded in SQL                                | yes         |

`_benchmark_calcs` does not read the goals sheet despite its name, so a
threshold can exist twice with two values. `_current` is the only consumer of
the region/school/grade granularity; the other two discard it.

### Benchmark is two different things under one `goal_type`

`*_total` rows carry full granularity and a `pct_goal` — real attainment goals.
Section-level rows (`*_ebrw`, `*_math_section`, `act_*`) are a single network
row each with `min_score` only and no `pct_goal` — threshold definitions, not
goals. Same `goal_type`, different shape, and the second kind is what makes
empty rows undeletable (see the attempts section above).

### `min_score` never varies within a score type and tier

Verified across every group: one distinct `min_score` per
(`expected_score_type`, `expected_goal_subtype`). The threshold is a pure
function of those two, yet it is duplicated across all 12 rows of
`sat_total_score`. It belongs in a lookup keyed on that pair, not repeated per
granularity.

Current values, and how they compare to the SY26-27 strategy doc:

| Scope           | Score type                         | HS-Ready | College-Ready |
| --------------- | ---------------------------------- | -------- | ------------- |
| SAT             | `sat_total_score`                  | 890      | 1010          |
| SAT             | `sat_ebrw`                         | 450      | 480           |
| SAT             | `sat_math`                         | 440      | 530           |
| PSAT 10 / NMSQT | `psat10_total` / `psatnmsqt_total` | 840      | 910           |
| PSAT 10 / NMSQT | `*_ebrw`                           | 420      | 430           |
| PSAT 10 / NMSQT | `*_math_section`                   | 420      | 480           |
| PSAT 8/9        | `psat89_total`                     | **800**  | 860           |
| PSAT 8/9        | `psat89_ebrw`                      | 400      | 410           |
| PSAT 8/9        | `psat89_math_section`              | 400      | 450           |
| ACT             | `act_composite`                    | 17       | 21            |
| ACT             | `act_math` / `act_reading`         | 17       | 22            |

Every total-level threshold matches the strategy doc except **PSAT 8/9 HS-Ready,
which the sheet has at 800 and the doc at 790.**

### Dropping region and school is lossless for the PSATs, not for SAT

All three PSAT totals carry an identical `pct_goal` at network, region, and
school level, so collapsing them loses nothing. SAT grade 11 genuinely varies —
College-Ready is 0.22 at network, 0.17-0.24 by region, 0.15-0.30 by school;
HS-Ready is 0.45 at network against 0.30-0.55 by school. SAT grade 12 is
uniform.

Grade level is also load-bearing for SAT: College-Ready is 0.22 at grade 11 and
0.17 at grade 12. Those are two cohorts, not two grades, which is why a
reformatted sheet needs a cohort or grade key rather than dropping the dimension
outright.

### Two cohort fields, both official, and the models disagree

`int_extracts__student_enrollments` carries both `graduation_year` and
`ktc_cohort`. **This is not a data-quality problem — KIPP Forward and KIPP
Foundation each use one**, so a goal's denominator depends on whose goal it is.

They diverge. AY2025 high school, one row per student per year:

| Grade | `graduation_year` null | Differs from `ktc_cohort` | Of those, retained |
| ----- | ---------------------- | ------------------------- | ------------------ |
| 9     | 4                      | 1                         | 1                  |
| 10    | 5                      | 21                        | 8                  |
| 11    | 2                      | 18                        | 10                 |
| 12    | 0                      | 19                        | 2                  |

`ktc_cohort` has no nulls in any grade; retention explains only 21 of the 59
differences.

`_benchmark_calcs` filters `graduation_year is not null` and never references
`ktc_cohort`, while `_current`, `_over_time`, `_scores`, and `_roster` all carry
both. On `_benchmark_calcs`' own filter set that means, for AY2025, 6 of 594
students dropped and **31 (~5%) attributed to a different graduating class than
the rest of the dashboard uses**. Five points is more than the gap between two
consecutive years of goal (22% to 28%), so it can move reported attainment more
than a year of progress.

Do not "fix" this by unifying the fields. The requirement is that a goal
declares which basis it is measured on, so both goal sets can live in one table
and each gets the right denominator.

## Unreported practice administrations in Illuminate

**Illuminate holds two more years of practice SAT than the dashboard shows.**
Practice reporting stops at AY2023, but `int_assessments__response_rollup` has
seven further administrations. KIPP Forward is not believed to have aligned on
these, so their status is a question rather than a defect — recorded here so
nobody rediscovers them and assumes data loss.

| Year | `assessment_id` | Title                                          | `scope` | Students |
| ---- | --------------- | ---------------------------------------------- | ------- | -------- |
| 2024 | 178628          | `SAT-24-25-BOY SAT-11th Grade-Math`            | `SAT`   | 369      |
| 2024 | 178629          | `SAT-24-25-BOY SAT-11th Grade-ReadingWriting`  | `SAT`   | 378      |
| 2024 | 187284          | `11th Grade - Practice SAT 2 EBRW`             | null    | 386      |
| 2024 | 187287          | `11th Grade Practice SAT 2 MATH`               | null    | 378      |
| 2024 | 187816          | `11th Grade Practice SAT 2 MATH (w/ Grid Ins)` | null    | 374      |
| 2025 | 204089          | `SAT-25-26-BOY SAT-11th Grade-Math`            | null    | 342      |
| 2025 | 204090          | `SAT-25-26-BOY SAT-11th Grade-ReadingWriting`  | null    | 347      |

178628 and 178629 follow the same naming convention as the SY26-27 assessments,
and 204089 / 204090 were administered in September 2025.

They fail for two independent reasons. **All seven are absent from
`act_scale_score_key`**, so the conversion join yields no scale score. **Five
also carry a null `scope`**, which the `scope in ('ACT', 'SAT')` filter rejects
regardless. So 178628 and 178629 would surface on sheet rows alone; the other
five need both.

The practical consequence: the account that practice administration moved
entirely to Winward for two years is incomplete. BOY practice SAT continued in
Illuminate through SY24-25 and SY25-26 at roughly 350-390 students per
administration, plus a MOY round in spring 2025. Backfilling would take
conversion rows for those forms, which means asking KIPP Foundation whether the
scale-score tables still exist.

## Recorded deviation — one corrected scale score

**The practice scale-score sheet knowingly diverges from its published source in
exactly one cell**, and no automated check can detect it, so it is recorded
here.

College Board's PSAT 8/9 Practice Test 1 scoring guide is non-monotonic at the
top of the Reading and Writing table: raw 65 converts to 710, but raw 66 — a
perfect section — converts to 700. A student answering every question correctly
would score ten points below one who missed a question. Verified against the
rendered PDF, so it is an error in the published table rather than a
transcription slip.

For assessment 226308 (SY26-27 PSAT 8/9 Reading and Writing), **raw 66 is
entered as 720**, which is both that row's own `UPPER` value and the section
maximum.

Two consequences worth knowing when reconciling a score against the guide:

- A PSAT 8/9 Reading and Writing score of 720 is ours; the guide says 700.
- Setting that cell aside, PSAT 8/9 cannot reach its scale maximum anyway —
  Reading and Writing tops out at 710 and Math at 690, so a perfect raw score
  converts to 1410 rather than 1440. That is published behavior, not an entry
  error. PSAT 10 does reach 1520.

Scale scores throughout the sheet come from the guides' `LOWER` column, the
established convention, so reported scores sit at the bottom of College Board's
published range rather than mid-range.

## Known issue — duplicate kippadb test records

**A long-standing source problem, not a modeling bug.** It is recorded here so
that anyone reading a CARAT number knows it is understood rather than
undiscovered. This is not the only duplication in the assessment data; it is the
one traced end to end so far.

### What it is

In `int_kippadb__standardized_test_unpivot`, 87 SAT sittings appear twice. Each
pair is **two distinct Salesforce record ids** sharing the same contact, test
date, and score — one real sitting entered twice. Measured on `sat_total_score`:

| Copies per sitting | Sittings | Every copy is a separate Salesforce record |
| ------------------ | -------- | ------------------------------------------ |
| 1                  | 3,401    | yes                                        |
| 2                  | 87       | yes, all 87                                |

The duplication is confined to SAT. PSAT 8/9, PSAT 10, PSAT NMSQT, and ACT show
none. Because the SAT unpivots into three score types, each duplicated sitting
produces three duplicated rows — `sat_ebrw`, `sat_math`, and `sat_total_score` —
for 258 excess rows reaching the reporting layer.

### Two distinct effects

**Averages were understated.** Before deduplication the SAT average on the
landing-page view read 1013.41 where the deduplicated value is 1017.84 — roughly
four points low, because the duplicated sittings happen to carry below-average
scores. Now fixed in `_scores`.

**Attempt counts are still inflated.** `rn_highest` in the official hub ranks
the two copies as separate attempts, visible as rank patterns `1,2`, `1,3`, and
`2,3`. Anything counting the hub with `count(*)` therefore credits a
double-entered sitting as two attempts — including the `alt_attempts` CTE in
`_over_time`, which is the count that actually determines the reported Attempts
figure. Up to 87 students may read as having taken one more SAT than they did,
which can move them across an `Attempts` goal threshold. **This is not fixed.**

### Where it is and is not handled

| Layer                                                | Status                                                |
| ---------------------------------------------------- | ----------------------------------------------------- |
| Salesforce / kippadb source                          | Not fixed — the real fix is deduplicating the records |
| `int_kippadb__standardized_test_unpivot`             | Not deduplicated                                      |
| `int_assessments__college_assessment` (official hub) | Not deduplicated                                      |
| `rpt_tableau__college_assessment_dashboard_scores`   | **Deduplicated**, with a guarding uniqueness test     |
| Attempt counts in `_over_time`                       | Not fixed                                             |

Deduplicating in `_scores` was chosen over a source-layer fix so the reported
averages stop being wrong today, without masking the problem where other
consumers read it. The inline `TODO` in the model names the source fix so the
workaround can be removed once the records are cleaned up.

### One case that is not a duplicate

Exactly one student has two rows with the same `score_type` and `test_date` but
**different** scale scores. That is a genuine source disagreement, not a
duplicate, so `scale_score` is deliberately part of the deduplication key and
both rows survive. Collapsing on the three-column key would silently discard one
of the two scores.
