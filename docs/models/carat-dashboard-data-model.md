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
