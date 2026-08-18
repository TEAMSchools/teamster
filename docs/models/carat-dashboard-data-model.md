# CARAT Dashboard Data Model

Reference for the College Admission Readiness Assessments Tracker (CARAT)
Tableau workbook and the dbt models behind it.

## What is CARAT?

CARAT is the KIPP Forward dashboard for the **tests and courses colleges use in
admission decisions**. It covers three families, so the name's "assessments" is
broader than entrance exams — two of the three are coursework:

| Family                 | Test | Course | What it covers                                                             |
| ---------------------- | ---- | ------ | -------------------------------------------------------------------------- |
| **Entrance exams**     | yes  | no     | SAT, PSAT 8/9, PSAT 10, PSAT NMSQT, historical ACT — official and practice |
| **Advanced Placement** | yes  | yes    | AP course enrollment and the exam score that can earn college credit       |
| **Dual enrollment**    | no   | yes    | College courses taken for credit in high school, and their grades          |

AP is the one that is both, which is why its model carries the
course-versus-exam combination as its own column — a student can take the course
without sitting the exam, or sit the exam without taking the course, and
colleges read those differently.

For each family it reports what a student has done and how it compares to a bar
— scores, participation, benchmark attainment, and progress against KIPP
Forward's goals.

**The population differs by view, and "recent cohorts" would be wrong for most
of them.** Only two are scoped to the current year; the other five carry every
cohort the warehouse holds:

| View                             | Students | Graduation years | Scoping                                                |
| -------------------------------- | -------- | ---------------- | ------------------------------------------------------ |
| `_current`                       | 2,110    | 2026–2030        | current year only                                      |
| `_roster`                        | 1,929    | 2027–2030        | current year, and only graduation years ahead          |
| `_scores`                        | 4,661    | 2011–2029        | **every cohort** — no year filter                      |
| `_benchmark_calcs`               | 6,707    | 2010–2030        | **every cohort** — only the thresholds are year-scoped |
| `_over_time`                     | 6,970    | 2010–2030        | **every cohort** — no year filter                      |
| `_de`, `ap_assessment_dashboard` | —        | full history     | no year filter                                         |

Measured 2026-08. So a trend view reaching back to the class of 2010 is working
as intended, not pulling in stale data — and a cohort filter is the reader's
job, not the model's.

This matters most when reconciling a percentage across views. `_current` and
`_over_time` answer the same question over populations that differ by more than
three times, so the same metric legitimately reports two different numbers
depending on which view is open.

The three families answer the same question and are read side by side in one
workbook, but they do not share a pipeline. Entrance exams have two score
pipelines meeting in a hub, a goals sheet, and a threshold scaffold; AP and dual
enrollment have none of that. Sections below are grouped by pipeline rather than
by family, so the entrance-exam machinery dominates — that reflects where the
complexity is, not what the dashboard is for.

## Models behind the workbook

The `college_admission_readiness_assessments_tracker_carat` exposure declares
seven models. All seven are documented below.

| Model                                                       | Purpose                                    | Grain                             |
| ----------------------------------------------------------- | ------------------------------------------ | --------------------------------- |
| `rpt_tableau__college_assessment_dashboard_scores`          | Score-level detail for average-score views | student × attempt                 |
| `rpt_tableau__college_assessment_dashboard_current`         | Current-year goal attainment               | student × goal                    |
| `rpt_tableau__college_assessment_dashboard_over_time`       | Multi-year goal trend                      | student × goal × score shape      |
| `rpt_tableau__college_assessment_dashboard_roster`          | Student roster with participation counts   | student × expected administration |
| `rpt_tableau__college_assessment_dashboard_benchmark_calcs` | Benchmark thresholds and attainment        | student × scope × subject × tier  |
| `rpt_tableau__college_assessment_dashboard_de`              | Dual enrollment course grades              | student × DE course               |
| `rpt_tableau__ap_assessment_dashboard`                      | AP course enrollment and exam results      | student × year × AP subject       |

The first five are the entrance-exam family, and only they were touched by the
practice work. `_de` and the AP model belong to the dashboard's purpose but not
to its pipeline — no hub, no goals sheet, no threshold scaffold, no practice
concept. Read the grouping below as by-pipeline, not by-importance.

Three further models exist in the repo but are `enabled: false` and are not part
of the workbook — `rpt_tableau__college_assessment_dashboard`,
`_dashboard_historic`, and `_qc_report`.

### Resolved — the hubs now share one vocabulary

Both hubs use the same convention: `test_type` is `Official` or `Practice`, and
`scope` is the test itself.

| Source                                         | `test_type`            | `scope`                                |
| ---------------------------------------------- | ---------------------- | -------------------------------------- |
| `int_assessments__college_assessment`          | `Official`             | ACT, PSAT 8/9, PSAT NMSQT, PSAT10, SAT |
| `int_assessments__college_assessment_practice` | `Practice`             | ACT, PSAT 8/9, PSAT10, SAT             |
| `stg_google_sheets__kippfwd__scaffold`         | `Official`, `Practice` | ACT, PSAT 8/9, PSAT NMSQT, PSAT10, SAT |

The practice hub used to hold the reverse — the test in `test_type`, and
Illuminate's unusable `Benchmark`-or-null in `scope` — which meant joining or
unioning the hubs on either column silently mis-grouped rather than erroring.
That is gone. The conversion sheet's column was renamed `Test_Type` to `scope`,
`test_type` now comes from the scaffold's `expected_test_type` (always
`Practice`, since the join filters to it), and the union no longer translates
anything.

!!! warning "Predicates key on `scope`, not `test_type`"

    Anything selecting a specific test — the total row's `score_type`, the ACT
    average, the benchmark folds — must read `scope`. `test_type` is a constant
    within each hub, so a predicate like `test_type = 'ACT'` is never true and
    fails silently. That mistake produced a null `score_type`, a `Combined`
    subject area on ACT, and a summed ACT composite reading 4-102 instead of an
    averaged 1-36 before it was caught.

Older PR and issue text still describes the swapped shape; treat this table as
current.

### Two score pipelines

Every question about CARAT numbers starts with which pipeline is involved. They
stay separate until `int_assessments__all_college_assessments`, which unions
them; from there down, `test_type` is what tells them apart:

| Pipeline | Hub model                                      | `test_type` | Origin                                           |
| -------- | ---------------------------------------------- | ----------- | ------------------------------------------------ |
| Official | `int_assessments__college_assessment`          | `Official`  | kippadb and College Board                        |
| Practice | `int_assessments__college_assessment_practice` | `Practice`  | Illuminate plus the conversion and scaffold tabs |

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
int_assessments__all_college_assessments     (both hubs — official and practice)
int_extracts__student_enrollments            (region, school, grad year, cohort)
        └─ rpt_tableau__college_assessment_dashboard_scores
```

The model is a single `select` with one join and no CTEs — the simplest of the
six. It adds no calculation; all aggregation happens in Tableau.

### Grain

One row per student per attempt. Roughly 29,000 official rows plus 1,100
practice, across about 4,600 students and graduation years 2011 through 2029.

### Behavior worth knowing

**Both test types appear here.** The model reads
`int_assessments__all_college_assessments`, so `test_type` holds `Official` and
`Practice`, and the workbook's row header separates them. Practice contributes
AY2023 ACT today — 1,103 rows across composite, math and reading.

**Both Score Category measures average over the same rows, and that is
deliberate.** The workbook toggles the measure between `scale_score`, each
attempt's own score, and `max_scale_score`, that student's best for the score
type. Both average over the full population of attempts, so a student who tested
twice counts twice under either measure. Do not "fix" that by filtering
`rn_highest = 1` — the whole point of the `scale_score` option is to see every
attempt, and both measures share one row set.

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
`dbt_utils.deduplicate` on `student_number`, `test_type`, `score_type`,
`test_date`, and `scale_score`, which is lossless because those columns
functionally determine every other projected column. A uniqueness test on the
same key guards it, so new non-identical duplicates upstream fail loudly instead
of shifting a reported average.

`test_type` is in that key because practice and official reuse the same
`score_type` strings — `sat_math`, `sat_ebrw` — so a student could legitimately
hold both on one date at one score. Without it the dedupe would collapse a real
pair, and the uniqueness test would fail on what the dedupe correctly kept.

**A small number of rows carry no graduation year.** Fewer than ten. They fall
out of any grad-year-grouped view silently rather than appearing in an unknown
bucket.

## `rpt_tableau__college_assessment_dashboard_current`

### What it powers

Current-year goal attainment — the "are we on track this year" views. One row
per enrolled high school student per goal.

### Lineage

```text
int_google_sheets__kippfwd__goals_unpivot   (goals paired with thresholds, By Grade branch)
int_assessments__all_college_assessments    (scores and attempt counts, both pipelines)
int_extracts__student_enrollments           (the enrolled population)
        └─ rpt_tableau__college_assessment_dashboard_current
```

### Grain

One row per student per goal, at `academic_year = current_academic_year`.
Roughly 111,000 rows over about 2,100 students, split evenly between `Official`
and `Practice`.

### Behavior worth knowing

**The academic year comes from the var, on every branch.** This is the rollover
this work exists for — production previously hardcoded AY2025 on four benchmark
branches while the attempts branch read the var, so the live report served
attempts a year ahead of benchmarks. See _Annual rollover_ below.

**`granularity_level` is gone.** The model was five near-identical union
branches emitting one row per student per granularity level; it is now one
branch, and the workbook aggregates its school, regional and network views from
student rows. `district` carries the network level.

!!! warning "A `KTAF` total is Camden and Newark only"

    The report is high school, Paterson has no high school grades, and Miami is
    not on Illuminate so its practice scores are untrackable. `district` reads
    `KTAF` regardless, so the label is wider than the population it covers.

**An attempts score of 0 is not the same as null.** The `scored_students` CTE
supplies a literal zero for any student holding any result of that test type,
and the score reads null where they hold no result at all. That is what keeps
the attempts denominator to test takers rather than to every enrolled student —
about 1,320 of 2,110. Treating a non-tester as 0 moves the denominator to 2,110
and roughly halves every reported percentage, with no error and no row-count
change. This is the single most dangerous thing in the model to get wrong.

**Only a total-level Benchmark is grade-specific.** The goals join reads
`expected_goal_type = 'Attempts' or expected_aligned_subject_area != 'Total' or grade_level = expected_grade_level`.
Attempts and section thresholds apply to every student regardless of grade — a
grade 9 student has sat the SAT zero times, which is a reportable answer.
Getting this wrong fails in both directions: requiring a grade match on Attempts
cuts them to a quarter of their rows, and letting null-grade rows apply to
everyone inflated Practice totals by 4,028 rows before the rule was narrowed.

**`benchmark_tier` replaces four `met_min_board_*` flags** with a three-way band
— College-Ready, HS Grad-Ready, or No Benchmark Met. Every board threshold
turned out to be a scaffold value already, so `Board` was a duplicate encoding.

!!! warning "`expected_test_type` is in the `benchmark_tier` partitions"

    Both `met_college_ready` and `met_hs_ready` partition by `student_number`,
    `expected_test_type` and `expected_score_type`. Official and Practice share
    one `score_type` vocabulary, so without the test type a practice score
    raises the official row's readiness band and vice versa. This shipped
    without it once and was caught in review. Never remove it.

For what moved against production, see _Why the current dashboard's numbers
change_ below.

## `rpt_tableau__college_assessment_dashboard_over_time`

### What it powers

Multi-year goal trend — attainment by graduating class rather than by current
year. Unlike `_current` it projects neither grade level nor cohort, which is why
the goals sheet carries separate `_over_time` percentage columns.

### Lineage

```text
int_google_sheets__kippfwd__goals_unpivot   (All Grades branch, filtered by rpt_consumers)
int_assessments__all_college_assessments    (max score and attempt_lifetime)
int_extracts__student_enrollments           (population, no year filter)
        └─ rpt_tableau__college_assessment_dashboard_over_time
```

### Grain

One row per student per goal per distinct score shape. About 558,000 rows over
roughly 6,970 students — 40 goal rows per student per test type, plus 326 extra
Official rows where `strategy_case` emits two rows for one score type.

### Behavior worth knowing

**It selects its own goals by name.** The `goals` CTE unnests `rpt_consumers`
and filters to this model, so a goal row reaches this view only if the unpivot
lists it. Adding a goal means adding this model to that array, not editing this
file.

**There is no academic-year filter.** The population is every enrolled high
school student across all years, which is what makes it a trend view. `_current`
is the year-scoped counterpart.

**Two columns named for test type mean different things.** `expected_test_type`
is the goal side and is always populated; `test_type` is the score side and is
**null where the student holds no matching score**. A null `test_type` is a
non-tester, not a defect — the same null-versus-zero semantics `_current`
handles with `scored_students`.

**It no longer suppresses the 27 scores `_benchmark_calcs` still hides.** The
`scores` CTE reads the hub through `max(scale_score)` with no `rn_highest`
filter, so scores whose rank was spent on a row later dropped for a missing test
date return here. The two views deliberately disagree on those students until
the benchmark view is repointed. See _Known issue — `rn_highest = 1` discards
scores_.

**Five `met` flag variants exist because the workbook asks the question at five
grains** — by score type, by aligned subject, by aligned scope and subject, and
`alt_` variants that treat `1 Attempt` as an equality rather than a threshold.
Every one partitions by `expected_test_type`.

For what moved against production, see _Why the over-time dashboard's numbers
change_ below.

## `rpt_tableau__college_assessment_dashboard_roster`

### What it powers

The student-level roster — one row per student per expected administration, so
Tableau renders a complete testing progression rather than a ragged one, with
participation counts and College and Career course context alongside.

### Lineage

```text
stg_google_sheets__kippfwd__expected_assessments      (the forced scaffold, rn = 1)
int_tableau__college_assessment_roster_scores         (the score, long on score_category)
int_students__college_assessment_participation_roster (lifetime attempt counts)
int_assessments__college_assessment                   (SAT highlight columns)
base_powerschool__course_enrollments                  (College and Career section)
int_extracts__student_enrollments                     (population)
        └─ rpt_tableau__college_assessment_dashboard_roster
```

### Grain

One row per student per expected administration per score category, for
currently enrolled high school students whose graduation year is in the future.

### Behavior worth knowing

**The population is forward-looking.** The filter
`graduation_year >= current_academic_year + 1` excludes students who have
already graduated, unlike `_over_time`, which keeps every cohort.

!!! warning "The participation join binds `test_type`"

    The join to `int_students__college_assessment_participation_roster` carries
    `p.test_type = 'Official'` alongside `p.rn_lifetime = 1`. That roster's
    grain now includes `test_type`, so `rn_lifetime = 1` alone returns one row
    per test type and duplicates every roster row for any student with practice
    data. The counts on this view are Official only, deliberately — the column
    names say so.

**The expected-assessment join is on region and `rn = 1` only.** It does not
bind grade, so every student in a region gets every administration the tab
states for that region. Narrowing happens on the score side, through
`expected_unique_test_admin_id` and `expected_score_category`.

**`sat_highlights` replaces three separate joins** to
`int_assessments__college_assessment` that differed only by subject area. One
conditional aggregation, one scan, value-identical. `rn_highest = 1` already
yields one row per student per subject area, so the `max()` picks rather than
collapses.

**These columns read `No Data`, not null, when a student has no CCR course** —
`ccr_course`, `ccr_teacher_name` and `ccr_section` are coalesced to that string,
so a Tableau filter on them needs the literal rather than a null test.

## `rpt_tableau__college_assessment_dashboard_benchmark_calcs`

### What it powers

Benchmark threshold attainment — whether each student has met the HS Grad-Ready
and College-Ready bar for each test and subject.

### Lineage

```text
stg_google_sheets__kippfwd__scaffold       (thresholds, unpivoted to two tiers)
int_assessments__all_college_assessments   (the benchmark score pick)
int_extracts__student_enrollments          (population)
        └─ rpt_tableau__college_assessment_dashboard_benchmark_calcs
```

### Grain

One row per student per scope per subject area per tier — a cross join, so every
student in the population gets every scaffold combination whether they tested or
not. About 241,000 rows over roughly 6,700 students.

### Behavior worth knowing

**Thresholds are data now, not a hardcoded `CASE`.** The scaffold's
`hs_grad_ready_min_score` and `college_ready_min_score` are unpivoted into two
tiers. `EA/ED-Ready` is retired, and PSAT 8/9 HS Grad-Ready reads 790 rather
than the hardcoded 800 — which moves 20 students to `Met`.

**ACT is excluded.** The scaffold filter is `expected_scope != 'ACT'`, so this
view has no ACT rows at all. `ACT/SAT` folds to `SAT` for the scopes that
remain.

**Practice can never satisfy an official benchmark.** The score join binds
`expected_test_type` to the hub's `test_type`, and the hub's
`rn_highest_benchmark_aligned_scope` partitions on `test_type` too. That pairing
is what made it safe to let practice reach this view — the risk flagged during
design was precisely that a practice score would outrank an official one.

**It reads `benchmark_aligned_scope_max_score`, which keeps its `rn_highest = 1`
filter**, so 27 students holding eligible scores still read `No Data` here. That
matches production deliberately and is why this view and `_over_time` disagree.

**`met_benchmark_goal` is a three-way string, not a boolean** — `No Data`, `Met`
or `Not Met`. `No Data` depends on a null score rather than on a threshold, so
lowering a threshold can never move anyone into or out of it.

For what moved against production, see _Why the benchmark dashboard's totals
change_ below.

## `rpt_tableau__college_assessment_dashboard_de`

### What it powers

Dual enrollment course grades. This model shares the workbook and the exposure
with the assessment views but none of the pipeline — no scaffold, no goals, no
hub, no practice concept.

### Lineage

```text
stg_powerschool__storedgrades           (the driving table)
stg_powerschool__students               (student number and name)
stg_powerschool__u_storedgrades_de      (the DE detail — course, score, institution)
        └─ rpt_tableau__college_assessment_dashboard_de
```

### Grain

One row per stored-grade record for a course whose name ends in `(DE)`, with
`storecode` in `Y1` or `Q2`. There is no academic-year filter — it is full
history.

### Behavior worth knowing

!!! warning "`unique_identifier` is not unique"

    It is `student_number || '_' || course_number`, which carries neither
    academic year nor store code. A student taking the same DE course in two
    years, or holding both a `Q2` and a `Y1` row for one course, collides. Do
    not use it as a key.

**There is a live `TODO` in the model about exactly that.** DE institutions now
submit grades twice yearly (fall to `Q2`, spring to an unsettled code). If
spring grades land on `Y1` in the same academic year, a student holds both a
`Q2` and a `Y1` row for the same course and the view duplicates. The store-code
policy is unresolved; a priority or fallback CTE is the anticipated fix.

**Every join is a `LEFT JOIN` from stored grades**, including the one to
`stg_powerschool__u_storedgrades_de`, whose `de_course_name is not null`
predicate sits in the `ON` clause. So a `(DE)`-named course with no DE detail
record still produces a row, with every `de_*` column null.

## `rpt_tableau__ap_assessment_dashboard`

### What it powers

AP course enrollment and exam results — which students took which AP courses,
which sat the exam, and what they scored. Documented here because the CARAT
exposure owns it; the ingest side has its own protocol, in
`.claude/skills/collegeboard-ap-data-ingest-protocol/SKILL.md`.

### Lineage

```text
base_powerschool__course_enrollments                 (AP course enrollment)
int_assessments__ap_assessments                      (exam scores)
stg_google_sheets__collegeboard__ap_course_crosswalk (course-name resolution)
int_extracts__student_enrollments                    (population)
        └─ rpt_tableau__ap_assessment_dashboard
```

### Grain

One row per student per academic year per AP subject code. The `subjects` CTE
builds that spine with a `union distinct` of two sources — subjects reached
through course enrollment and subjects reached through an exam record — so a
student who sat an exam without enrolling in the course still appears.

### Behavior worth knowing

**A student can legitimately hold two rows for one AP subject.** A main AP
course plus a companion recitation section are two distinct course offerings,
not a data error, and they are deliberately left undeduped. This is separate
from the PowerSchool double-write corpus in
[#3900](https://github.com/TEAMSchools/teamster/issues/3900).

**`test_subject_area` encodes the course-versus-exam combination**, which is the
column most of the workbook's logic keys on:

| Course | Exam | `test_subject_area`                     |
| ------ | ---- | --------------------------------------- |
| no     | no   | `Not applicable`                        |
| yes    | no   | `Took course, but not AP exam.`         |
| no     | yes  | `Took AP exam, not enrolled in course.` |
| yes    | yes  | the AP course name                      |

**The population filter is an exam-date containment test, not a year equality.**
`date(academic_year + 1, 05, 01) between entrydate and exitdate` requires the
student to have been enrolled on 1 May, when AP exams are administered. A
student who withdrew in March is excluded from that year even though they hold
an enrollment record for it.

**`Calculus BC: AB Subscore` is filtered out** of `ap_assessments`. It is a
derived subscore rather than a separate exam, and leaving it in would double a
BC student's exam count.

**`expected_scope` and `expected_test_type` are literals**, reading
`Not applicable` or `AP` and `Official`. They exist so the workbook can union
this view alongside the college-assessment views on a shared field name; they
carry no practice concept.

## Annual rollover

The rollover is what issue
[#4658](https://github.com/TEAMSchools/teamster/issues/4658) was opened for. The
code side is now a single variable, but the data side is several sheet edits,
and the failure mode on the data side is silent.

### The code side

`current_academic_year` in `src/dbt/kipptaf/dbt_project.yml`, updated each July.
Four CARAT models read it:

| Model              | Reads the var for                                 |
| ------------------ | ------------------------------------------------- |
| `_current`         | the enrolled population, on the single branch     |
| `_benchmark_calcs` | the scaffold's threshold year                     |
| `_roster`          | the population, plus `graduation_year >= var + 1` |
| `_dashboard`       | disabled — not part of the workbook               |

`_over_time`, `_scores`, `_de` and the AP model do not read it. `_over_time` and
`_scores` are deliberately all-years; `_de` has no year filter at all; the AP
model derives its own May containment date from each enrollment row's
`academic_year`.

The variable is network-wide, not CARAT-specific — bumping it moves every model
in the project that reads it, so a rollover is never a CARAT-only change.

### The data side

!!! warning "A missing scaffold year drops everything, silently"

    The conversion-to-scaffold join is INNER and keyed on `academic_year`,
    `scope` and `score_type`. A year with no scaffold rows therefore yields no
    practice output and raises no error — the same class of defect this work
    removed from the old `act_scale_score_key` join. Nothing downstream
    complains; the practice pipeline simply reports nothing.

Per year, in this order:

1. **Illuminate sessions must exist for the new raw academic year.** Practice
   assessments reach `int_assessments__scaffold` only through its
   `where not is_internal_assessment` branch, which inner-joins student session
   affiliation on the **raw** year — the spring year, so 2027 for SY26-27.
   Without sessions the whole chain is empty regardless of everything below.
   This is owned outside the data team and is the item with a real deadline.
1. **Scaffold rows for the new year** — one per section plus one per total, per
   administration. Run _Procedure: Add scaffold rows_ in the skill.
1. **Scale Score Conversion rows** for each new practice assessment. Run
   _Procedure: Add practice assessments for a new administration_.
1. **Goals sheet rows** carrying the new `academic_year`. Every current row is
   AY2026; goal horizon is not yet modelled.
1. **Expected Assessments tab**, only if the testing calendar moved. Regenerate
   the whole tab rather than editing it — see _Procedure: Rebuild the Expected
   Assessments seasons tab_, which explains why a partial edit is silent.

### Verifying a rollover landed

`_current` is the view to check, because it is the one that broke. Every row
should carry the new year, and the split between `Official` and `Practice`
should be even:

```sql
select
    academic_year,
    expected_test_type,
    count(*) as n_rows,
    count(distinct student_number) as n_students,
from `teamster-332318.kipptaf_tableau.rpt_tableau__college_assessment_dashboard_current`
group by academic_year, expected_test_type
```

More than one `academic_year` in that result means a branch is reading a
different year from the rest, which is the production defect this work fixed.

## The practice pipeline — three pieces

Practice scores are assembled from two KIPP Forward sheet tabs plus one model,
and the division of labour matters because both tabs live in the same workbook
and it is easy to put something in the wrong one:

| Piece                                                         | Owns                                                               |
| ------------------------------------------------------------- | ------------------------------------------------------------------ |
| `stg_google_sheets__kippfwd__practice_scale_score_conversion` | raw-score-to-scale-score bands, one row per band per assessment    |
| `stg_google_sheets__kippfwd__scaffold`                        | the vocabulary — subject alignments, course discipline, cut scores |
| `int_assessments__college_assessment_practice`                | joins the two, converts responses, builds composites               |

The rule of thumb: if a value repeats across every band of an assessment, it is
vocabulary and belongs in the scaffold. If it varies band to band, it belongs in
the conversion sheet. `subject_area`, `aligned_subject_area` and
`course_discipline` all moved out of conversion into scaffold for exactly that
reason.

`score_type` is the seam. It stays in **both** — it is the only column whose
spelling is identical on each side, so it is what joins them. `subject` cannot:
conversion says `Mathematics` and `Reading and Writing` where the scaffold says
`Math` and `EBRW`. The scaffold's `expected_practice_test_subject` carries
conversion's spelling if you ever need to bridge the other way.

## `stg_google_sheets__kippfwd__scaffold`

The assessment vocabulary — every valid combination of academic year, test type,
scope, and score type, with its subject alignments and cut scores. 41 rows
across AY2023 and AY2026, Official and Practice.

Grain is (`academic_year`, `expected_test_type`, `expected_scope`,
`expected_grade_level`, `expected_score_type`), enforced by a composite
uniqueness test. **`expected_grade_level` is part of the key** because AY2023
ran two SAT forms at once — a three-section form for grades 9-10 and the
two-section digital form for grade 11 — so `sat_math` and `sat_total_score` each
appear twice that year, differing only in grade.

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

`expected_aligned_subject_area` merges **both** ways — Composite and Combined to
Total, _and_ ACT Reading to EBRW/Reading. The assessment hub splits those across
two columns: `aligned_subject_area` folds only to Total, and `aligned_subject`
folds both. So despite the matching name, the scaffold's column is the hub's
`aligned_subject`, not its `aligned_subject_area`.

A consumer needing the hub's narrower framing has to derive it.
`int_google_sheets__kippfwd__goals_unpivot` does, with an `if()` on
`expected_subject_area`. Passing the scaffold's column straight through under
the hub's name is a silent relabel — EBRW rows read `EBRW/Reading` where the
report expects `EBRW`, and it type-checks and builds clean.

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

**Four score types carry no cut scores anywhere**, Official or Practice:
`act_english`, `act_science`, `sat_reading_test_score`, and
`sat_writing_and_language_test_score`. The goals sheet only ever defined ACT
composite / math / reading and the SAT section pair, so those nulls are correct
rather than missing data.

## `stg_google_sheets__kippfwd__practice_scale_score_conversion`

Raw-score-to-scale-score bands, one row per band per assessment. 835 rows across
20 assessments. Membership here is what designates an Illuminate assessment as a
reportable practice assessment.

Supersedes `stg_google_sheets__kippfwd__act_scale_score_key`, which reads the
same rows from an `ACT Scale Score Key V1` tab under PascalCase headers. Both
sources still exist so the old one can be retired separately; **production still
reads the old one until this work merges**, so deleting the V1 tab early breaks
the nightly build.

### Two derived columns worth understanding

**`aligned_scale_score`** is `scale_score` put onto the section's reporting
scale, so downstream sums need no per-grade adjustment. It differs only for the
123 grade 9-10 SAT Reading and Writing rows, which College Board stores as
legacy _test scores_ on a 10-40 scale rather than section scores on 200-800.
Rescaled by ten they run 100-400 each, so the pair sums to the 200-800 EBRW
equivalent and a three-section total lands on 400-1600 alongside Math's native
200-800. The model reads `aligned_scale_score` and does no rescaling of its own.

**`expected_total_subjects_tested`** is how many sections an administration
expects — 4 for ACT, 3 for the legacy grade 9-10 SAT, 2 for everything else. It
is constant within an administration, which the composite gate depends on. It
replaced hardcoded counts and grade filters in the model.

### Gotchas

**`sheet_range` is the tab name, not a named range.** The named range on that
tab is sheet-scoped (`'Scale Score Conversion'!<name>`), which BigQuery cannot
resolve, and the qualified form breaks the generated DDL on the embedded quote.
A workbook-scoped range would work; sheet-scoped ones appear when a tab is
duplicated, which is how both this tab and `Goals` got theirs.

**The explicit `columns:` list is positional.** An external table with a
declared schema maps columns to sheet columns in order, so inserting a column in
the middle of the tab without inserting it at the same position in
`sources-external.yml` silently shifts every value after it into the wrong
column. Same-typed neighbours make that invisible.

**`score_type` must not be removed.** It looks redundant next to `subject`, but
it is the join key to the scaffold.

## Adding a practice administration — what to touch

1. Enter the conversion bands in `Scale Score Conversion`, including
   `aligned_scale_score`, `score_type`, and `expected_total_subjects_tested`.
   The `carat-dashboard` skill has the generator and the audit procedure.
1. Add a scaffold row per section **and one per total**, with
   `expected_test_type = 'Practice'`. A missing scaffold row silently drops
   those conversion rows, because the model's join is inner.
1. Check that `score_type` matches exactly on both sides. That is the only key.
1. Confirm `expected_total_subjects_tested` equals the number of sections you
   entered, or no composite will ever be produced for that administration.

## Goal type — Attempts

Attempt goals answer "what share of students sat this test at least once, and at
least twice."

### The sheet was rebuilt — thresholds and percentages are now separate

`stg_google_sheets__kippfwd__goals` used to do two jobs at once: declare which
score types exist, and declare which have targets. That is why rows with a null
`pct_goal` were load-bearing — `_current` inner joins the sheet on `score_type`
alone, so deleting an empty row dropped a score type from the dashboard.

That is resolved. The sheet now carries **only percentages**, one column per
metric, and the thresholds live on `stg_google_sheets__kippfwd__scaffold` as
`a1_attempt_min_score`, `a2_plus_attempts_min_score`, `hs_grad_ready_min_score`
and `college_ready_min_score`. A consumer needs both models to evaluate a goal,
and `int_google_sheets__kippfwd__goals_unpivot` is the model that pairs them.

Two consequences worth knowing:

`min_score` no longer carries two meanings. It used to be an attempt count on an
Attempts row and a scale score on a Benchmark row, so no comparison could be
written generically against it. Each threshold now has its own named column on
the scaffold.

Goals are no longer differentiated by region or school. KIPP Forward stopped
setting them that way, so `region` and `schoolid` are gone from the sheet
entirely rather than sitting null.

### Shape

The sheet is wide — `academic_year`, `test_type`, `grade_level`, `cohort`,
`score_type`, then one column per metric — and staging unpivots it to long, so a
goal is identified by:

```text
(academic_year, test_type, grade_level, score_type, expected_metric_type,
 is_over_time_goal)
```

`expected_metric_type` holds the sheet's own column names (`pct_1_attempt`,
`pct_2_plus_attempts`, `pct_hs_grad_ready`, `pct_college_ready`). Two derived
columns reproduce the vocabulary the reporting views already key on:
`expected_goal_type` is Attempts or Benchmark, and `expected_goal_subtype` is
`1 Attempt`, `2+ Attempts`, `HS Grad-Ready` or `College-Ready`.

`is_over_time_goal` is why the key has six columns rather than five. The sheet
carries two extra percentage columns, `pct_hs_grad_ready_over_time` and
`pct_college_ready_over_time`, holding a cohort-independent goal for
`_over_time`, which reports on neither grade level nor cohort and so cannot use
a per-grade goal. Staging strips the `_over_time` suffix, so those rows land
under the same four `expected_metric_type` values and the flag says which
framing a row is. Stripping keeps the two CASEs above at four arms — the new
rows inherit `Benchmark` and `HS Grad-Ready` automatically instead of needing
new branches that could be missed.

The practical consequence: **anything reading this model that does not filter
the flag sees both framings.** `int_google_sheets__kippfwd__goals_unpivot`
filters it on both branches. A view still reading staging directly must add
`where not is_over_time_goal` or it double-counts every SAT and PSAT benchmark.

Those four subtype strings are spelled out rather than derived. They disagree on
separator — a space for attempts, a hyphen for ready — and on casing, and `HS`
is an initialism that `initcap` renders as `Hs`. No regex reaches all four; the
retired tiers `EA-Ready` and `ED-Ready` were initialisms too, so the exception
is the norm here.

### Adding a metric is a data change, not a schema change

Because staging unpivots, a fifth metric column on the sheet becomes rows rather
than columns. Two things must move with it: the `expected_goal_type` and
`expected_goal_subtype` CASEs, which have no `else` and will read null for an
unnamed metric — deliberately, so a new column surfaces rather than being folded
silently into an existing family.

An `_over_time` variant of an existing metric is the exception: the suffix strip
lands it on a name both CASEs already handle, so only the sheet and the source
`columns:` block change. That is the point of stripping rather than carrying the
raw column name.

UNPIVOT drops nulls, so a metric blank for a given row produces no row at all
rather than a row with a null goal. Every PSAT row is blank for
`pct_2_plus_attempts`, since those tests are administered once, and those rows
are simply absent.

### What is tracked

All current rows are AY2026. Attempts are tracked at 95% for one attempt across
PSAT 8/9, PSAT10, PSAT NMSQT and SAT; only SAT carries a two-or-more target, at
80% official and 95% practice. Practice is higher because a practice
administration is scheduled rather than something a student registers for.

### The attempt count is now measured on distinct dates

`attempt_lifetime` and `yearly_attempts_totals` on
`int_assessments__all_college_assessments` count distinct `test_date` per
student, test type and score type, on total rows only. This replaces counting
rows, which credited a double-entered sitting as two attempts — see _Known issue
— duplicate kippadb test records_.

`dense_rank` on `test_date` is what makes it work: duplicate dates share a rank,
so the max of the rank is the distinct-date count. `row_number` or `count(*)`
would both overcount.

### The participation roster reads those fields rather than deriving counts

`int_students__college_assessment_participation_roster` used to pivot scope
counts per year, running-sum them, then take a max for a lifetime figure — and
separately unpivot and re-pivot the goals into twelve columns via a concatenated
metric key. All of that is gone. It reads `attempt_lifetime` and
`yearly_attempts_totals` and pivots them once.

`test_type` and `academic_year` are now part of its grain. `academic_year`
matters because a student repeating a grade holds two years at one grade level,
which the old grain merged into one row. `test_type` matters because the goals
join is keyed on it, so practice rows pick up the practice target rather than
the official one.

**A consumer wanting only official participation must filter `test_type` as well
as `rn_lifetime = 1`.** `rn_lifetime` is partitioned by student and test type,
so a student with both returns one row of each.

The goal columns it carries still have no consumer — all four readers take only
`*_count_lifetime` and `rn_lifetime`. They are kept for the reporting views to
pick up rather than dropped.

## Goal type — Benchmark

Benchmark goals answer "what share of students scored at or above a threshold."

### Which models read them

| Model                                                       | How                                                              | In workbook |
| ----------------------------------------------------------- | ---------------------------------------------------------------- | ----------- |
| `rpt_tableau__college_assessment_dashboard_current`         | `int_google_sheets__kippfwd__goals_unpivot`, `By Grade` branch   | yes         |
| `rpt_tableau__college_assessment_dashboard_over_time`       | `int_google_sheets__kippfwd__goals_unpivot`, `All Grades` branch | yes         |
| `rpt_gsheets__college_assessments_long`                     | `int_google_sheets__kippfwd__goals_unpivot`, `All Grades` branch | no          |
| `rpt_tableau__college_assessment_dashboard_benchmark_calcs` | `stg_google_sheets__kippfwd__scaffold`, thresholds unpivoted     | yes         |

`_benchmark_calcs` does not read the goals sheet despite its name, so a
threshold can exist twice with two values. `_current` is the only consumer of
the region/school/grade granularity; the other two discard it.

### Benchmark is two different things under one `goal_type`

`*_total` rows carry a grade and a `pct_goal` — real attainment goals.
Section-level rows (`*_ebrw`, `*_math_section`, `act_*`) carry `min_score` only,
at no grade — threshold definitions, not goals. Same `goal_type`, different
shape.

That distinction is now structural rather than incidental.
`int_google_sheets__kippfwd__goals_unpivot` reads both from the scaffold, and
`grade_level` is null on exactly the second kind, because it comes from the
goals side of the join. `_current` keys its grade predicate on that: only a
total-level Benchmark is grade-specific.

### `min_score` never varies within a score type and tier

Verified across every group: one distinct `min_score` per
(`expected_score_type`, `expected_goal_subtype`). The threshold is a pure
function of those two, yet it is duplicated across all 12 rows of
`sat_total_score`. It belongs in a lookup keyed on that pair, not repeated per
granularity.

Current values, and how they compare to the SY26-27 strategy doc:

| Scope           | Score type                         | HS Grad-Ready | College-Ready |
| --------------- | ---------------------------------- | ------------- | ------------- |
| SAT             | `sat_total_score`                  | 890           | 1010          |
| SAT             | `sat_ebrw`                         | 450           | 480           |
| SAT             | `sat_math`                         | 440           | 530           |
| PSAT 10 / NMSQT | `psat10_total` / `psatnmsqt_total` | 840           | 910           |
| PSAT 10 / NMSQT | `*_ebrw`                           | 420           | 430           |
| PSAT 10 / NMSQT | `*_math_section`                   | 420           | 480           |
| PSAT 8/9        | `psat89_total`                     | 790           | 860           |
| PSAT 8/9        | `psat89_ebrw`                      | 400           | 410           |
| PSAT 8/9        | `psat89_math_section`              | 400           | 450           |
| ACT             | `act_composite`                    | 17            | 21            |
| ACT             | `act_math` / `act_reading`         | 17            | 22            |

Every total-level threshold now matches the SY26-27 strategy doc. PSAT 8/9 HS
Grad-Ready was the one exception, at 800 on the sheet against 790 in the doc;
the rebuilt scaffold has it at 790.

The rebuilt sheet also corrected an inverted PSAT 8/9 percentage pair. The
retired sheet had HS Grad-Ready at 0.34 against a threshold of 800 and
College-Ready at 0.60 against 860 — a harder bar with a higher expected share.
The per-grade columns now read 0.50 and 0.30, and the over-time columns read
0.60 and 0.30, keeping the retired sheet's two values with the pair the right
way round. PSAT10 and NMSQT were never inverted, so this was specific to PSAT
8/9.

### Dropping region and school is lossless for the PSATs, not for SAT

All three PSAT totals carry an identical `pct_goal` at network, region, and
school level, so collapsing them loses nothing. SAT grade 11 genuinely varies —
College-Ready is 0.22 at network, 0.17-0.24 by region, 0.15-0.30 by school; HS
Grad-Ready is 0.45 at network against 0.30-0.55 by school. SAT grade 12 is
uniform.

Grade level is also load-bearing for SAT: College-Ready is 0.22 at grade 11 and
0.17 at grade 12. Those are two cohorts, not two grades, which is why a
reformatted sheet needs a cohort or grade key rather than dropping the dimension
outright.

The rebuilt sheet keeps the grade key, and grade now pairs one-to-one with
cohort — grade 12 is cohort 2027, grade 11 is cohort 2028. So the two SAT rows
are goals for two different cohorts, both correct, not a conflict.

That left `_over_time` with no right answer, since it projects neither grade nor
cohort. Prod cross joins the whole goal set, so those two rows arrive as two
indistinguishable rows per student differing only in `pct_goal` — 42 goal rows
per student where there are 40 distinct combinations, with Tableau resolving the
pair by `MIN()`. That is where the dashboard's 35% HS Grad-Ready and 17%
College-Ready come from: the grade 12 value, picked by aggregation rather than
by decision.

The `_over_time` columns replace that. One cohort-independent goal per benchmark
metric is stated on the sheet, `_over_time` reads it directly, and the per-grade
rows are untouched for the views that do report on grade.

Those columns are currently set to **the goals the dashboard already displays**,
so the reported goal lines hold steady while the provenance changes — SAT at
0.35 and 0.17, PSAT10 and NMSQT at 0.55 and 0.28, all matching prod exactly.
PSAT 8/9 is the one departure, at 0.60 and 0.30, because prod's pair was
inverted. They are deliberately **not** the topline per-cohort goals; KIPP
Forward has not yet stated a cohort-independent goal, so the placeholder is the
status quo rather than a guess. Do not reconcile them against the strategy doc's
per-cohort table.

No pick happens in SQL, and `test_kippfwd_goals_over_time_collapse` fails if a
collapse ever becomes a pick again — either an `_over_time` goal stated
inconsistently across a score type's grade rows, or a per-grade goal that
disagrees with no `_over_time` goal to override it.

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

## `int_google_sheets__kippfwd__goals_unpivot`

Pairs each goal with the threshold it is measured against, so a consumer reads
one model instead of joining two sheets.

### Two branches, because the reporting views disagree on grain

The model is a `UNION ALL` of two branches. `goal_branch` names which one a row
belongs to and is what a consumer filters on; `rpt_consumers` names the views
that read each. **Edit the branch your view is listed on** — that column is the
record of what else the edit moves.

| `goal_branch` | Grade handling                     | `rpt_consumers`                |
| ------------- | ---------------------------------- | ------------------------------ |
| `By Grade`    | `grade_level` from the goals sheet | `_roster`, `_current`, `_wide` |
| `All Grades`  | `grade_level` null throughout      | `_over_time`, `_long`          |

Both are driven from the scaffold, so both carry every threshold it states
rather than only those a goal was written for, and both apply the same two
exclusions. They differ only in how a goal's grade is treated.

`goal_branch` is in the uniqueness key for that reason: the branches agree on
every other key column wherever they overlap. `grade_level` being null on one
side separates them today, but only incidentally.

**Filter `goal_branch`, not `rpt_consumers`, from an intermediate.**
`rpt_consumers` is an `ARRAY<STRING>` whose job is declaring blast radius to BI
— a consumer selects from it with `cross join unnest(rpt_consumers)` and filters
the plain column, so appending a consumer never changes an existing filter. But
an upstream model filtering on a _view name_ couples its own output to that
view's existence, which is the wrong dependency.
`int_students__college_assessment_participation_roster` filters `goal_branch`
for this reason.

### Which grade a row carries, and why it comes from the goals sheet

`grade_level` is taken from the goals side of the join, not the scaffold. Three
consequences, all of them reproducing the retired sheet's shape:

- A score type with goals at two grades **fans to one row per grade**. SAT
  states separate grade 11 and grade 12 targets, so `sat_total_score` appears
  twice per metric. That is the grain the grade-reporting views report at.
- A threshold with no goal stated for it reads **null grade**. That is every
  section row, because the rebuilt sheet states no section goals — and it
  matches how the retired sheet carried section thresholds at no grade, which is
  what let every student be measured against every section bar regardless of
  their own grade.
- The join therefore does **not** key on grade, and the scaffold's
  comma-separated `expected_grade_level` list is not read at all. An earlier
  version split that list and joined on it; taking grade from the goal instead
  removed the split and its trimming.

Mapping the scaffold's column names onto the goals vocabulary is a CASE, because
the two sides spell the same concept differently — `hs_grad_ready_min_score`
against `pct_hs_grad_ready`. If the staging model is ever renamed to a neutral
vocabulary, that CASE disappears and both sides simply agree.

### Attempts exist only at the total grain, on both branches

An attempt is one sitting of a test, recorded on the total row. A section row is
a slice of that same sitting and carries no attempt count of its own.

The scaffold does not encode this: it sets `a1_attempt_min_score` to 1 and
`a2_plus_attempts_min_score` to 2 on **every** row, sections included. Reading
those literally invents goal combinations the report has never had — prod's goal
set contains zero Attempts-on-section rows, so the rule below reproduces prod's
Official set rather than imposing a new judgment:

```sql
where
    expected_score_category != 'Score Change'
    and (
        expected_goal_type = 'Benchmark'
        or expected_aligned_subject_area = 'Total'
    )
```

Benchmark rows are kept at every grain, sections included, because prod has 20
of those. Row math out of the scaffold unpivot: 126 rows, less 2 score-change,
less 44 Attempts-on-section, leaves 80 on the All Grades branch. By Grade lands
at 88, the difference being SAT fanning to two grades where the sheet states two
goals.

`expected_score_category` is the scaffold's purpose-built level-versus-change
flag, which is why the growth exclusion keys on it rather than on
`expected_grouping`. Both markers work today, but `expected_grouping`'s primary
job is subject bucketing with `Growth` layered on as a special case. This is
**not** dead code: of the scaffold's two growth rows, one carries populated
attempt thresholds, so the predicate removes 2 rows that `UNPIVOT` would
otherwise emit.

### A goal with no scaffold row does not appear

Both branches being scaffold-driven means a goal whose score type has no
scaffold row is absent entirely, rather than surviving with a null threshold as
it did when the by-grade branch was goals-driven.
`test_kippfwd_goals_resolve_to_scaffold` surfaces those instead, so a stated
goal cannot go silently unreported.

`psat10nmsqt_total` fails that test today — a combined PSAT10 and PSAT NMSQT
goal with no scaffold equivalent, five rows counting its over-time pair. Adding
one means widening the scaffold's `expected_scope` accepted values to admit
`PSAT10/NMSQT`, since a combined row has no single honest scope. It has no
consumer today: `_current` never reported it, and the roster's PIVOT enumerates
five labels that do not include it.

### `expected_metric_label` is not unique per row

The model carries a scope-and-metric token — `sat_1_attempt`,
`psat89_hs_grad_ready` — so a consumer can PIVOT to one column per metric. It
reproduces the vocabulary the retired sheet derived through an 18-branch CASE.

It repeats across grades on the By Grade branch. Grades 11 and 12 both carry
`sat_total_score`, so each SAT label appears twice. The Attempts metrics hold
the same threshold and target at both grades, so aggregating over the label is
safe for those. **The Benchmark metrics do not** — grade 11 and 12 differ on the
target, so a PIVOT grouping on the label alone averages two grades into one
wrong number. Keep `grade_level` in the grouping for anything Benchmark.

`expected_metric_name` is the separate, display-facing label `_over_time` reads,
and it is not interchangeable with the token above. Benchmark rows carry the
subtype alone — `HS Grad-Ready` — while Attempts rows carry the scope too,
`SAT 2+ Attempts`, because an attempt count means nothing without naming the
test. Both columns are derived once in the final select and so hold the same
values on either branch.

## `int_assessments__college_assessment_practice`

The practice hub. Illuminate responses converted to scale scores through two
KIPP Forward sheets: `practice_scale_score_conversion` holds the raw-to-scale
bands, and `scaffold` holds the vocabulary. Membership in the conversion sheet
is what designates an Illuminate assessment as a reportable practice assessment
— Illuminate's own `scope` is not used, because externally created assessments
carry `Benchmark` or null rather than the test name.

### Three row types

| `response_type` | Grain                          | Built from                |
| --------------- | ------------------------------ | ------------------------- |
| `Group`         | one per response group         | Illuminate `group` rows   |
| `Subject`       | one per student per assessment | Illuminate `overall` rows |
| `Total`         | one per student administration | aggregated `overall` rows |

Illuminate supplies only `group` and `overall` rows. `Subject` and `Total` are
both derived from `overall`, which is never emitted as itself.

`Subject` is the section grain the official hub uses, so it is what the
assessments hub consumes. `Group` rows carry the response-group detail and are
excluded from the hub. Group rows have no scale score of their own — Illuminate
splits a section into ~4.7 response groups whose `points` are subsets — so they
borrow the score from their `overall` sibling through a window function rather
than a self-join.

**`overall` is per subject, not the composite.** Each Illuminate assessment is
one subject, so a student's `overall` rows carry the section score types
(`act_english`, `act_math`, …) and never a total. `act_composite` and its
siblings exist nowhere upstream — the `Total` branch produces them from `scope`,
because the conversion sheet has no total bands to join.

### The composite gate

A `Total` row's `scale_score` is produced only when
`actual_total_subjects_tested` equals `expected_total_subjects_tested`, the
latter carried per administration in the conversion sheet. ACT averages its
sections, everything else sums them — the same
`if(scope = 'ACT', avg(…), sum(…))` shape the official hub uses for
`superscore`. The row itself is always emitted; only the score is nulled, so an
incomplete sitting stays visible.

Counting sections rather than naming them is what makes this general, but the
count alone is not sufficient: it is partitioned by academic year, student,
`scope_round` **and `grade_level`**. Grade is load-bearing because AY2023 ran
two SAT forms concurrently — a three-section form for grades 9-10 and the
two-section digital form for grade 11 — both under `scope_round = 'SAT1'`. Four
students actually sat sections from both forms in one round; without grade in
the partition their sections pool and produce an invalid total, which is what
production did.

`scope_round` rather than `administration_round` is deliberate. The sheet's
round-within-year (`SAT1`, `SAT2`, `ACT1`, `PSAT891`, `PSAT101`) is reliable;
`administration_round` is a month-and-year derived from Illuminate's
`administered_at`, which is null on every externally created assessment. The
sheet column was renamed from `Administration_Round` to `scope_round` so the two
stop reading as the same thing.

The composite is built with `group by`, not `select distinct` over window
functions. That is deliberate: `course_discipline` and `test_date` vary within
the partition, so `distinct` cannot collapse them and emits one row per distinct
value — production held 2,103 composite rows for 1,252 student-rounds for
exactly this reason. Any new branch must aggregate or stamp those columns
constant.

### Things that will bite you editing this model

**`WHERE` runs before window functions.** The section rows borrow their score
from the `overall` sibling via
`max(if(response_type = 'overall', …)) over (partition by … assessment_id)`, and
that window must be computed in the `responses` CTE, where both row types are
present. Computing it in a select that already filters
`where response_type = 'group'` returns null on every row — silently, with no
error, because the condition is never true over the surviving partition.

**`grouping` is a BigQuery reserved word.** The scaffold's `expected_grouping`
needs backticks when aliased to `grouping` (`GROUPING SETS`).

**The conversion-to-scaffold join keeps a `select distinct`.** It joins on
(`academic_year`, `scope`, `score_type`), and the scaffold's uniqueness key
includes `expected_grade_level` while this join deliberately omits grade. No
(`academic_year`, `scope`, `score_type`) currently has more than one scaffold
row, so the `distinct` is a no-op today — it guards a future administration that
needs different vocabulary per grade, which would otherwise match two rows and
fan out silently.

**`rn_highest` excludes Group rows from its partition, not just its output.**
The `if()` nulls the rank on Group rows, but `response_type` also sits in the
partition. Drop it and Group rows compete with their Subject sibling — they
carry the same `score_type` and the same `scale_score`, so they tie and split
the ranks. Measured: 290 of 1,438 Subject rows lose rank 1. The same reasoning
applies to `is_benchmark_eligible` in the assessments hub's benchmark rank.

### Changes when this version replaces the AY2023-era model

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

## `int_assessments__all_college_assessments`

The hub unioning the official and practice hubs so the CARAT reporting views
read one source, with calculations that were repeated across those views moved
upstream. Modelled on `int_amplify__all_assessments`: union heterogeneous
sources into one column set, then compute rankings over the union rather than
within each source.

Practice enters at the `Subject` and `Total` grain
(`where response_type != 'Group'`), matching official's one-row-per-subject
shape. Response-group detail stays in the practice hub.

Nine columns are official-only and read null on practice rows —
`aligned_subject`, `salesforce_id`, the two score-shape counts, `surrogate_key`,
and the four superscore fields. They are computed inside the official hub rather
than below the union.

`strategy_case` and `previous_total_score_change` were on that list until the
practice hub gained its own, so both now populate for either test type.

The practice hub supplies `is_overall_score`, `is_subject_score`,
`max_scale_score`, and `running_max_scale_score` itself, matching the official
definitions, so those four populate for both test types. `is_overall_score` and
`is_subject_score` key on `response_type` there rather than on `subject_area` as
official does — official has no group rows to exclude, and inferring from
`subject_area` would tag every group row as a subject score.

### Fields moved upstream

| Field                                             | Status                                                             |
| ------------------------------------------------- | ------------------------------------------------------------------ |
| `rn_highest`                                      | **done** — each hub computes its own, the union passes it through  |
| max score by aligned scope                        | **done** — `benchmark_aligned_scope_max_score` plus a row tag      |
| `benchmark_aligned_scope`, `aligned_subject_area` | **done** — derived here for both branches, or data in the scaffold |
| `max_scale_score`                                 | **done** — each hub computes its own                               |
| the `met_min_score_int_*` family                  | `_over_time`, five window variants                                 |
| attempt counts                                    | **done** — `attempt_lifetime` and `yearly_attempts_totals`         |

Prune rather than move: `superscore`, `avg_running_max_superscore` and
`sum_running_max_superscore` have one consumer between them, and
`runnning_superscore` (three n's) has none.

### The benchmark pick lives here, not in the reporting view

`_benchmark_calcs` used to select the winning score itself, with an
`aligned_scores_pre` CTE reading the **official hub only** and a
`dbt_utils.deduplicate` over (student, aligned scope, subject area). Both moved
here, so official and practice get one definition instead of two:

| Column                               | What it is                                        |
| ------------------------------------ | ------------------------------------------------- |
| `is_benchmark_eligible`              | excludes ACT and the four sub-test score types    |
| `rn_highest_benchmark_aligned_scope` | `= 1` tags the winning row; the view filters this |
| `benchmark_aligned_scope_max_score`  | the same winner as a value, carried on every row  |

Three things about the partition, each load-bearing:

- **`subject_area`, not `score_type`** — PSAT10 and PSAT NMSQT carry different
  score types (`psat10_ebrw` against `psatnmsqt_ebrw`) but the same subject
  area, so partitioning on score type would keep them apart and defeat the fold.
- **`test_type`** — without it a practice score competes with an official one
  and can win, which would move reported college-ready attainment. This is what
  makes feeding practice into the benchmark view safe, and it is why the earlier
  `across_test_types` variant of the max was deleted rather than renamed.
- **`is_benchmark_eligible`** — a `row_number()` still assigns ranks to rows the
  `if()` later nulls, so ineligible rows would consume ranks from eligible ones.
  A `max()` needs no such guard, since it ignores nulls.

### The two folds do different jobs

Getting this backwards produces numbers that look plausible and are meaningless.

| Fold                | Used for                     | Why it is valid                                                                                                                                                                                      |
| ------------------- | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PSAT10 + PSAT NMSQT | maxing **scores**            | College Board considers them the same test, offered in different windows. Verified scale-compatible: EBRW 160-690 against 160-680, Math 160-680 against 160-740, Combined 320-1260 against 320-1370. |
| ACT + SAT           | **attainment booleans** only | "met the HS-ready or college-ready bar ever, by any route". Never a score comparison — ACT Math is 1-36 and SAT Math is 200-800.                                                                     |

So a precomputed max score folds only the PSATs, which is why the hub's version
is named `benchmark_aligned_scope`. The scaffold's `expected_aligned_scope`,
with its `ACT/SAT` value, belongs on the met-threshold flags instead. The two
are not interchangeable despite the near-identical names. A max partitioned on
`ACT/SAT` would silently return the SAT value for every student and rate an
ACT-only 36 against a 1010 threshold.

Both exclusions are now safe by construction, in `is_benchmark_eligible`: ACT
and the four sub-test score types (`psat10_math_test`, `psat10_reading`,
`sat_math_test_score`, `sat_reading_test_score`) are excluded in the hub rather
than by a `where` in the reporting view. `psat10_reading` carries
`subject_area = 'Reading'` on an 8-31 scale and would otherwise compete in a max
against real section scores.

`aligned_scope` is also carried on the practice hub, from the scaffold, so both
folds are available as data. It has no consumer yet — nothing supplies it
otherwise, so it is there for the attainment work.

!!! warning "One inconsistency remains"

    `_benchmark_calcs` folds `ACT/SAT` down to `SAT` in its own scaffold CTE and
    then joins `expected_aligned_scope = benchmark_aligned_scope`. That works only
    because the fold happens to produce the same string the hub's ACT-excluding
    max leaves behind. Joining on `expected_scope` would express the intent
    directly. Left as-is rather than changed blind, since the join drives every
    reported benchmark row.

### Resolved — the open decisions on this model have shipped

Three entries sat here describing work as still to do. All of it landed in the
CARAT rollover work, so they are recorded as done rather than pending:

- **Scores and attempts split in `_over_time`.** Its `score` column was a
  five-branch `CASE` inside an `avg()` holding either a scale score or an
  attempt count. It is now a two-branch `if()` keyed on `expected_goal_type`.
- **The participation round trip is gone.** `_over_time` no longer reads
  `int_students__college_assessment_participation_roster` at all; it derives
  `attempt_count_lifetime` from `attempt_lifetime` on the hub. Only
  `_dashboard_roster` and `rpt_gsheets__college_assessments_wide` still read the
  roster's wide `*_count_lifetime` columns.
- **The attempt-count fix landed upstream.** `alt_attempt_count_lifetime` no
  longer exists anywhere in the project. Attempts count distinct test dates on
  the hub, so duplicate Salesforce records no longer read as separate sittings.

## `int_tableau__college_assessment_roster_scores`

One row per administration the Expected Assessments tab expects of a student,
carrying the score they earned in it, for every current student graduating this
year or later. It spans a student's whole high school history rather than the
current year, because the roster dashboard reports progress across
administrations.

The tab drives it. A score sat in a month the tab does not list has nowhere to
land and does not appear — widening coverage is an edit to the tab, not to this
model.

### One join, not two pipelines

The model now reads `int_assessments__all_college_assessments`, so official and
practice arrive already reconciled to one vocabulary. The join binds
`expected_month_round` to the hub's `aligned_month_round`, which carries a month
name for official rows and a `scope_round` for practice, so a single predicate
serves both. That replaced a two-branch union whose SAT and PSAT halves were
near-identical.

Three bindings carry the weight, and one of them is deliberately asymmetric:

- **`test_type`** — a practice scaffold row matches a practice score only. This
  was previously unbound, which is what produced the fabricated practice rows
  described below.
- **`aligned_month_round`** — the administration a score belongs to. Previously
  bound on the SAT branch only.
- **`academic_year`, for SAT only.** Grades 11 and 12 both report a Winter
  season and both include December and January, so an unbound December score
  would attach to both grades' rows.

### Why every scope except SAT is unbound on year

PSAT NMSQT is normally sat in grade 11, but the tab carries it at grade 10 only.
150 current students sat it in grade 11, and their scores reach the report
solely because no year binds a score to the enrollment row supplying its season
— the student's grade 10 enrollment row, in a different academic year, matches
the grade 10 scaffold row and collects the score.

Binding the year would drop those 150. The alternative — adding a grade 11 NMSQT
row to the tab — is worse: the tab has no cohort dimension, so every row added
is expected of every student forever, and a grade 11 NMSQT row would read as a
missing assessment for every future student when nobody is expected to sit it
anymore.

The cost of forcing them onto the grade 10 row is bounded. Of the 150, 68 sat
NMSQT only in grade 11, so the grade 10 row is their single data point either
way. The other 82, all class of 2027, sat it in both grades and show their best
score rather than both administrations. Worth confirming with KIPP Forward
whether they want that split out. `TODO(#4658)`.

### Growth is measured in season order, and practice counts

The value on a `Score Change` row lags over `expected_admin_season_order`, not
test date, so it measures the seasons this report displays rather than every
sitting a student had. It is computed as `total_growth_score_change` inside the
model and reaches consumers as `score`, paired with that category. Season order
is reverse-chronological — 1 is the most recent — so ordering `desc` walks a
student's history forwards in time and `lag()` reads the earlier season.

Practice administrations are ordinary links in that chain. The grade 11 practice
SAT sits at order 17, the far end of the SAT sequence, so a grade 11 Winter
score's change is measured against it. Nothing in the model treats practice
specially; it follows from binding `test_type` correctly.

It stays restricted to SAT totals because those are the only administrations the
tab carries a Growth row for — grade 11 Winter and Spring, grade 12 Fall and
Winter. Subject growth becomes available the moment KIPP Forward adds those
rows.

The hub's own `previous_score_change` is deliberately **not** used here. It
chains every administration a student has, including the ones the tab lists
under `Not Official`, so a growth figure taken from it would be measured against
a score the dashboard does not show.

### It emits score categories long, so its consumers do not

The model has two consumers — `rpt_tableau__college_assessment_dashboard_roster`
and `rpt_gsheets__college_assessments_wide` — and both used to open with a
byte-identical CTE unioning the model to itself, once as `Scale Score` and once
as `Score Change`. That union now lives here, so each row carries `score` and
`score_category` and both views join straight through.

Folding the model into one of those views was the alternative, and it would have
forced the same 120 lines into the other. Two views got shorter instead.

The union is expressed as an `UNPIVOT`, which drops null rows, so an
administration with no growth produces no `Score Change` row rather than one
holding null. That is not a behavior change: a consumer left joining the
scaffold reads null either way. It does cut the row count — 7,791 `Scale Score`
rows plus 1,170 `Score Change`, against 15,582 when both categories were emitted
for every administration.

### What the repointing changed

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

## The two KIPP Forward Google Sheets extracts

`rpt_gsheets__college_assessments_long` and
`rpt_gsheets__college_assessments_wide` feed sheets KIPP Forward reads directly.
Both were official-only until practice was added; practice is kept separate from
official in each rather than mixed into it, because an attainment figure that
silently blends a practice sitting with a real one is worse than no figure.

### The long sheet carries a second type column, because the first one is taken

It reads `int_assessments__all_college_assessments` now, so practice rows arrive
alongside official ones. The discriminator is **`administration_type`**, holding
`Official` or `Practice`.

It could not be called `test_type`: that column already exists on this model and
holds the **scope** — SAT, PSAT10 — via `scope as test_type` in the final
select. Renaming it would break the enforced contract and every formula in the
live sheet, so the new column took a new name rather than the obvious one.

The change is purely additive. Official rows are identical to production scope
by scope — PSAT 8/9 2,367, PSAT NMSQT 1,251, PSAT10 1,254, SAT 2,561 — with 33
practice rows added.

Its goals join is guarded by `test_kippfwd_goals_long_join_grain`. The view
joins goals on test type and score type alone, with no academic year binding,
and resolves its pivot with `any_value()`, so a second academic year stating a
goal for a key that already has one would double every matching score row and
pick a threshold arbitrarily. The goals model spans AY2023 and AY2026 today and
stays unambiguous only because the 2023 rows are practice ACT while the 2026 ACT
rows are official — a property of the data, not the model. The model's own
uniqueness test carries `academic_year` and so cannot catch it.

### The wide sheet names practice columns rather than renaming official ones

Practice gets nine score columns, one per administration the tab carries — grade
9 PSAT 8/9, grade 10 PSAT10, grade 11 SAT, all Fall — plus three practice
attempt counts.

Existing columns keep their names. Renaming them to `*_official` for symmetry
was considered and rejected: the model is contract-enforced across 67 columns
and feeds a live sheet, so a rename changes 40 contract entries and 40 headers
under anyone with a formula referencing them, and buys only a label. The columns
have always been official-only and still are. **Every score column without
`practice` in its name is official.**

### Two defects the practice work surfaced

**The wide sheet was reporting practice sittings as official attempts.** It
joined `int_students__college_assessment_participation_roster` without filtering
`test_type`, a column that model only recently gained. Ten practice-only
students were carrying a practice sitting in `sat_count_lifetime`. With the
filter, `sat_count_lifetime` reconciles to production exactly minus the
documented 86-student duplicate correction.

**Its score columns keyed on score type, season and grade but not test type.**
No column collided only because no practice PSAT data exists yet — the tab
carries practice administrations at the same score type and grade as official
ones, so the first practice PSAT scores would have landed silently in official
columns. The score is now split by test type in the `roster` CTE, so each column
picks from one side or the other:

```sql
if(ea.expected_test_type = 'Official', a.score, null) as official_score,
if(ea.expected_test_type = 'Practice', a.score, null) as practice_score,
```

That shape was chosen over adding a predicate to each of the 39 `CASE` blocks,
which is the same fix applied 39 times and 39 chances to miss one.

### `sat_highlights` replaces three joins, on all three consumers

`_dashboard_roster`, and both sheets, each left joined
`int_assessments__college_assessment` three times — once for the SAT superscore,
once for the highest EBRW, once for the highest Math — differing only by subject
area. One CTE with conditional aggregation replaces all three, so each model
scans that source once instead of three times.

`rn_highest = 1` already yields exactly one row per student per subject area
(1,974 Total, 1,414 EBRW, 1,414 Math, no fan-out), so the aggregate picks rather
than collapses and every value is unchanged.

The aggregate would absorb a future fan-out silently rather than surfacing it as
duplicate rows. That is why `_dashboard_roster` now carries a uniqueness test on
`(student_number, expected_field_name_score_category)` — it had none at all
before, which repo convention requires of every `rpt_` model.

## Resolved — grade 9 and 10 AY2023 SAT is excluded from reporting

**Decision: those administrations are not valid and are not reported.** Ninth
and tenth graders should have sat PSAT 8/9 and PSAT 10, not a full SAT form, so
KIPP Forward excluded them.

The exclusion is implemented in the **scaffold sheet**, not in SQL: deleting a
Practice scaffold row for (`academic_year`, `expected_scope`,
`expected_score_type`) makes the conversion CTE's inner join drop every band for
it. All three AY2023 SAT practice rows are gone — `sat_math`, `sat_ebrw`, and
`sat_total_score`. AY2023 ACT stays; grade 11 ACT is valid and still reports 379
composites.

Two things worth knowing about how that landed:

- **The first attempt was incomplete.** Only the Reading and Writing score types
  were removed, and `sat_math` survived because grade 11 uses it too and the
  join omits grade. That left 737 Total rows with
  `actual_total_subjects_tested = 1` against `expected = 3` — a Math-only total
  that can never compute, null on every row. Removing `sat_math` was safe only
  because grade 11 AY2023 has **no data**: assessments 138849 and 138850 return
  zero rows from every layer of Illuminate, down to
  `stg_illuminate__dna_assessments__agg_student_responses_overall`. They were
  created and never administered.
- **The conversion bands were left in place.** They no longer join to anything,
  so they are inert. Delete them only if the sheet should stop implying those
  tests are reportable.

The rest of this section records why the labelling itself was correct, since
that question comes up independently.

Six of the eight AY2023 practice assessments are grade 9 and 10 but carried
`Test_Type = SAT`. That was not a typo.

**The data says they really are SAT.** The sheet's raw-score maxima match the
legacy paper SAT question counts exactly, and match no PSAT form:

| Section     | Sheet raw max (grades 9-10) | Legacy SAT | PSAT 8/9 | PSAT 10 / NMSQT |
| ----------- | --------------------------- | ---------- | -------- | --------------- |
| Reading     | 52                          | **52**     | 42       | 47              |
| Writing     | 44                          | **44**     | 40       | 44              |
| Mathematics | 58                          | **58**     | 38       | 48              |

The scale ranges corroborate it. Grades 9-10 store `Reading` and `Writing` on a
10-40 scale — the legacy SAT _test score_ scale — while `Mathematics` is native
200-800. Grade 11 (138849 / 138850) is the digital two-section form, 200-790 on
both sections.

So the labelling was right and the programme was wrong, which is what the
exclusion above resolves. SY26-27 assigns PSAT 8/9 to grade 9 and PSAT 10 to
grade 10, so current practice already uses the grade-appropriate tests.

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

## Post-merge verification

Every measured figure in the sections below was taken **before** the merge, from
a developer build compared against production. They were re-checked against
production itself on 2026-08-18, after the deploy, and the shape holds:

| Check                                        | Documented           | Production           |
| -------------------------------------------- | -------------------- | -------------------- |
| PSAT 8/9 Combined HS Grad-Ready threshold    | 790                  | 790                  |
| `EA/ED-Ready` present                        | retired              | absent               |
| `_current` distinct `academic_year`          | one, from the var    | one — 2026           |
| `_current` attempts denominator              | 1,319 of 2,090       | 1,320 of 2,110       |
| `_current` SAT 1 Attempt, of test takers     | 31.8%                | 32.0%                |
| `_over_time` goal rows per student           | 40                   | 40                   |
| `_over_time` Official `strategy_case` excess | 326 rows             | 326 rows             |
| Practice ACT composite rows                  | 379, 1:1             | 379, 1:1             |
| Practice rows on `_roster_scores`            | 30, over 10 students | 30, over 10 students |

The small upward drift in student counts is a live enrollment table in
mid-August — the population grows daily — not a modelling difference.
Percentages therefore move by tenths. **Ratios and structural counts are the
durable figures; absolute student and row counts are not.** Reconcile against
the shape, and against the guidance in _If you are reconciling and the numbers
do not match this table_.

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
duplicate kippadb test records_. Counting distinct test dates instead of rows
credits one sitting once. Almost all are Camden class of 2027 on the April 2026
school-day SAT.

This is the change most likely to be questioned, because that cohort's SAT
`2+ Attempts` rate is measured against an 0.80 goal and a student sitting
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

## Score change is measured two ways, and they are not interchangeable

| Column                        | Grain            | Crosses test types |
| ----------------------------- | ---------------- | ------------------ |
| `previous_total_score_change` | totals only      | **no**             |
| `previous_score_change`       | every score type | **yes**            |

`previous_total_score_change` is computed inside each hub, so it never sees the
other test type. Official keys it on test date, practice on `scope_round` —
because a school can split one practice administration across days, and two
administrations can therefore share a date. Practice reads null throughout
today, no student holding two practice administrations of one test.

`previous_score_change` is computed at the union, covers sections as well as
totals, and **deliberately omits `test_type` from its partition**. That is the
one place in this lineage where omitting it is correct: every other partition
carries it so a practice score can never displace an official one, but a
student's progression runs through both and chaining them is the point. 1,611
administrations currently follow a practice one across 342 students, mostly the
AY2023 practice-ACT cohort chaining into their official ACT. The scores stay
comparable because a practice score is converted onto the same scale as its
official counterpart.

It also measures between administrations rather than between rows. 261 official
sittings carry the same score twice under different `rn_highest`, so lagging
directly would read a change of zero between a row and its own duplicate.

**Nothing reads `previous_score_change` yet.** It exists for the
growth-over-time work due shortly after this PR, which reports change for totals
and subjects across all students.

### Subject-level growth is available at the hub and not yet reported

The reporting layer stays at total grain, matching what the roster reports
today. Extending it to sections needs three things that do not exist: growth
score types on the scaffold (`sat_ebrw_growth` and friends), matching rows on
the Expected Assessments tab, and a KIPP Forward decision that they want it. The
hub column is ready when they ask.

## Known issue — `rn_highest = 1` discards scores whose better sibling has no test date

**27 students read `No Data` in the benchmark view while holding eligible SAT
scores.** Not a duplicate-record problem and not a filter anyone wrote wrong —
it is an ordering accident between two models.

Root cause measured upstream: `int_kippadb__standardized_test_unpivot` holds 670
rows with a null date, and **342 of them carry `rn_highest = 1`** — the
student's top score for that score type. So the rank is spent on a row that gets
dropped. It only surfaces in 27 partitions because the benchmark max spans
several score types and collapses to null only when _no_ row in the partition
has rank 1. Every one is Official / SAT; practice contributes none, being all
ACT and therefore ineligible.

The upstream fix is Ops backfilling the dates in Salesforce, which is not
planned. The model-side fix is below.

`rn_highest` is ranked in the upstream unpivots,
`partition by (student, scope, score_type) order by score desc`. The official
hub then applies `where date is not null` when it unions those unpivots. So the
rank is assigned _before_ the row is dropped. When a student's highest score for
a score type carries no test date, that row is discarded and the surviving rows
keep their original ranks — `rn_highest = 2`, `3`, and so on, with no rank-1 row
anywhere in the hub for that student and score type.

Anything filtering `rn_highest = 1` therefore drops the student entirely rather
than falling back to their best surviving score. The filter now lives inside
`benchmark_aligned_scope_max_score` in the assessments hub, which
`_benchmark_calcs` reads, so those students still have no value to report and
`met_benchmark_goal` returns `No Data`.

Confirm the shape with an aggregate rather than by naming students:

```sql
select
    count(*) as partitions_with_no_rank_1,
from (
    select student_number, score_type, min(rn_highest) as min_rn,
    from `teamster-332318.kipptaf_assessments.int_assessments__college_assessment`
    where scope = 'SAT'
    group by student_number, score_type
)
where min_rn > 1
```

Affected partitions come back with `min_rn = 2` — the rank-1 row is absent, not
low-scoring.

**The filter is redundant to a `max()`.** `rn_highest = 1` marks the highest
score per (student, scope, score_type), and a max over a set equals a max over
that set's per-subgroup maxima — so on any partition at or above that grain, the
filter cannot change the result. Its only live effect is suppressing scores
whose better sibling was dropped for a missing date.

`int_assessments__all_college_assessments` **retains the filter deliberately**,
inside the `if()` feeding `benchmark_aligned_scope_max_score`, so that
repointing consumers onto it stays a provable no-op.

`rn_highest_benchmark_aligned_scope` does **not** carry the filter, so the tag
and the max disagree on exactly those 27 keys — the tag finds a winner where the
max returns null. Anything reading the tag and taking `scale_score` gets the
restored values; anything reading the max does not. Verified: 12,267 tagged rows
against 12,240 with a max, zero value mismatches where both produce one.

Removing the filter is a real correction. Measured impact on the benchmark view:
27 students across 51 threshold rows move from `No Data` to `Met`.

**It has partly shipped, contrary to the intent originally recorded here.**
`rpt_tableau__college_assessment_dashboard_over_time` replaced its direct score
join, which carried `and s.rn_highest = 1`, with a `max(scale_score)` CTE
reading the hub — and that dropped the filter as a side effect of the refactor
rather than as a decision. It was measured afterwards and kept, because
re-adding it would mean suppressing known-good scores to preserve a defect. The
"ship it visibly" requirement is met for that view by documentation instead of a
separate release, which is defensible only because the effect lands entirely on
grad years 2014, 2015 and 2022 and moves no live cohort. See _Why the over-time
dashboard's numbers change_.

`_benchmark_calcs` still suppresses, reading
`benchmark_aligned_scope_max_score`, which retains the filter. **The two views
now disagree on those 27 students** — expected, not drift — until the benchmark
view is repointed. That repoint is where the remaining visible change lives, and
it is still worth shipping on its own.

The alternative fix — moving the ranking downstream of the null-date filter, so
ranks are dense over surviving rows — is the more complete repair but changes
`rn_highest` for every consumer, and the hub's uniqueness test includes that
column.

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

Within what reaches the hub, the duplication is confined to SAT — PSAT 8/9, PSAT
10, PSAT NMSQT and ACT show none. Because the SAT unpivots into three score
types, each duplicated sitting produces three duplicated rows — `sat_ebrw`,
`sat_math`, and `sat_total_score` — for 258 excess rows reaching the reporting
layer.

That is a statement about the hub, not about kippadb. Checking
`stg_kippadb__standardized_test` directly turns up **478 duplicate PSAT records
from 2024**, the same shape — two records, one score, one date. They never reach
CARAT because the hub takes PSAT from College Board rather than Salesforce, but
they do affect anything reading kippadb standardized tests.

### It is one bad load, not scattered noise

Attributing the SAT duplicates to an administration: 86 of the 87 are **Camden,
class of 2027, the April 2026 school-day SAT** — 80 on 4/23 and 6 on 4/29. The
remaining one is a 2019 sitting. The other 32 students from that April
administration have a single clean record each, so the load hit a subset.

That concentration matters for reading the numbers. Camden 2027 is the senior
cohort, and their SAT 2+ attempts rate is measured against an 0.80 goal, so 86
double-counted sittings inflate a board-reported figure for one cohort rather
than adding noise everywhere.

An AP check using the same method finds **no** duplicates, but only once
`subject` is part of the key. Grouped on contact, date and test type alone,
1,548 students who legitimately sit several AP exams on one day read as 2,289
duplicates. Any duplicate-hunting query over this table must key on subject.

### Two distinct effects

**Averages were understated.** Before deduplication the SAT average on the
landing-page view read 1013.41 where the deduplicated value is 1017.84 — roughly
four points low, because the duplicated sittings happen to carry below-average
scores. Now fixed in `_scores`.

**Attempt counts were inflated.** `rn_highest` in the official hub ranks the two
copies as separate attempts, visible as rank patterns `1,2`, `1,3`, and `2,3`,
so anything counting the hub with `count(*)` credited a double-entered sitting
as two attempts. That is what `attempt_lifetime` and `yearly_attempts_totals` on
`int_assessments__all_college_assessments` now avoid — they count distinct test
dates, so a score filed twice on one date counts once.

### Where it is and is not handled

| Layer                                                | Status                                                |
| ---------------------------------------------------- | ----------------------------------------------------- |
| Salesforce / kippadb source                          | Not fixed — the real fix is deduplicating the records |
| `int_kippadb__standardized_test_unpivot`             | Not deduplicated                                      |
| `int_assessments__college_assessment` (official hub) | Not deduplicated                                      |
| `rpt_tableau__college_assessment_dashboard_scores`   | **Deduplicated**, with a guarding uniqueness test     |
| `attempt_lifetime` / `yearly_attempts_totals`        | **Immune** — counts distinct dates, not rows          |

Deduplicating in `_scores` was chosen over a source-layer fix so the reported
averages stop being wrong today, without masking the problem where other
consumers read it. The inline `TODO` in the model names the source fix so the
workaround can be removed once the records are cleaned up.

The counting fix and a source cleanup address the same rows from opposite ends,
so whichever lands first absorbs the correction and the other becomes a no-op
for these counts. When comparing attempt counts before and after either change,
record which happened first or the comparison cannot be interpreted.

### One case that is not a duplicate

Exactly one student has two rows with the same `score_type` and `test_date` but
**different** scale scores. That is a genuine source disagreement, not a
duplicate, so `scale_score` is deliberately part of the deduplication key and
both rows survive. Collapsing on the three-column key would silently discard one
of the two scores.
