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

**Duplicate rows inflate averages slightly.** The upstream hub distinguishes
some rows only by `rn_highest`, which this model does not project. Those rows
arrive identical on every projected column, so roughly 260 of the 29,000 rows —
under one percent — are exact duplicates. For a view whose only measure is an
average, a duplicated score is double-weighted. The effect is small but
non-zero, and it is inherited rather than introduced here.

**A small number of rows carry no graduation year.** Fewer than ten. They fall
out of any grad-year-grouped view silently rather than appearing in an unknown
bucket.

### Convention gaps

The contract is enforced through the `extracts/` directory default and the
properties file lists every column with its type. Two conventions are unmet:

- No uniqueness test, which `rpt_` models require. The natural key is not
  currently unique because of the inherited duplicates above, so adding one
  means either projecting `rn_highest` or deduplicating first.
- No `description` on the model or any column.
