# NJDOE Universal Screener Data Model

New Jersey requires districts to report universal literacy screener results for
students in grades K through 3. KTAF screens with DIBELS, administered through
Amplify, and `rpt_gsheets__njdoe_universal_screener_data` reshapes those results
into the columns the state's collection expects.

Exposure: `rpt_gsheets__njdoe_universal_screener_data` in
`src/dbt/kipptaf/models/exposures/google-sheets.yml`. The model writes to a
Google Sheet, which a person then submits to NJDOE. Nothing in this pipeline
talks to the state directly.

Grain: one row per student, benchmark period and assessment name. The full
composite key is `region`, `schoolid`, `school`, `benchmark_period`,
`district_code`, `school_code`, `sid` and `assessment_name`. A
`dbt_utils.unique_combination_of_columns` test guards `sid`, `benchmark_period`
and `assessment_name`, scoped to rows where `sid` is not null.

Upstream: `int_amplify__mclass__benchmark_student_summary` for the assessment
results and the school attributes, and `int_extracts__student_enrollments` for
the state student ID. Both are `ref()`s, so the lineage is complete.

## The six measures

Amplify's column names and the state's measure names do not match. The model
renames each one on the way through.

| Reported as            | Amplify measure                              |
| ---------------------- | -------------------------------------------- |
| `phonics_and_decoding` | Nonsense Word Fluency, words recoded correct |
| `letter_naming`        | Letter Naming Fluency                        |
| `phonemic_awareness`   | Phoneme Segmentation Fluency                 |
| `comprehension`        | Maze                                         |
| `oral_reading_fluency` | Oral Reading Fluency                         |
| `composite`            | DIBELS composite                             |

Each produces two output columns, a `_score` and a `_level`.

## Performance levels are recoded to the state's vocabulary

NJDOE does not use Amplify's benchmark wording, so the model translates it.

| Amplify level                                | Reported as         |
| -------------------------------------------- | ------------------- |
| Above Benchmark                              | `Above Grade Level` |
| At Benchmark                                 | `At Grade Level`    |
| Below Benchmark **and** Well Below Benchmark | `Below Grade Level` |
| tested out                                   | `TO`                |
| discontinued                                 | `D`                 |

**The two below-benchmark levels collapse into one.** Amplify distinguishes
Below Benchmark from Well Below Benchmark; this extract does not. That
distinction is not recoverable from the submitted file, so do not use this model
as a source for internal below-benchmark analysis. Use the DIBELS dashboard
lineage for that.

Tested-out and discontinued arrive as their own boolean columns per measure and
take precedence over the level. A student who tested out of a measure reports
`TO` whatever the level column said.

## Scope

The model is narrow on purpose. Every filter below is deliberate.

- New Jersey only, via `state = 'NJ'`. Miami is out of scope because Florida
  runs no equivalent collection.
- Grades K, 1, 2 and 3 only.
- Enrollment grade must equal the grade the student was assessed in. A student
  assessed off-grade is dropped rather than reported at either grade.
- The current academic year only, from `var("current_academic_year")`.
- One enrollment row per student per year, via `rn_year = 1`.

The enrollment join is an inner join, so a student Amplify has but the
enrollment extract does not is dropped silently. That is the failure mode that
emptied this extract once already — see _How this broke_ below.

## NJDOE identifiers are hardcoded

`district_code` and `school_code` come from a `CASE` statement on region, not
from a crosswalk.

| Region   | `district_code` | `school_code` |
| -------- | --------------- | ------------- |
| Newark   | `7325`          | `965`         |
| Camden   | `1799`          | `111`         |
| Paterson | `7899`          | `925`         |

One `school_code` covers every school in a region, so it is not a per-school
identifier.

!!! question "What does NJDOE expect in `school_code`?"

    A single hardcoded value per region suggests a district-level or LEA-level
    identifier rather than a per-school one. Confirm against the state's
    specification before trusting it.

## Students with no state ID

`sid` comes from the enrollment extract's `state_studentnumber` and can be null.
Those rows collapse together, because every other key column matches for
students at the same school in the same period.

NJDOE matches submissions on the state ID, so a null-`sid` row cannot be matched
on the state's side. As of the AY2026 Beginning-of-Year window this affected 3
students, one in each region. The uniqueness test excludes them deliberately —
they are a data-entry gap in PowerSchool, not a modelling defect.

## Shape of the transformation

Four steps, and the middle two exist only to move measures between rows and
columns.

1. Read the mClass intermediate, join to the enrollment extract for the state
   ID, and derive the NJDOE codes from region.
2. `UNPIVOT` the six measures from columns into rows, so the level recoding can
   be written once instead of six times.
3. Recode the levels, applying tested-out and discontinued first.
4. Two `PIVOT`s back into wide columns — one for scores, one for levels — joined
   on the full row key.

The double pivot is why scores and levels are assembled separately and then
rejoined, rather than travelling together.

## How this broke, and why the shape changed

Worth knowing, because the failure was silent and the fix is the reason the
model looks the way it does now.

The model used to read two raw Amplify datasets directly, as hardcoded dataset
paths rather than through a dbt source, and to take the student number from
`student_primary_id_studentnumber`.

Between AY2025 and AY2026 Amplify moved that identifier. The old column was
populated on all 8,150 AY2025 rows and on none of the 3,078 AY2026 rows; the
value arrived in `student_primary_id` instead. Two sibling ID fields moved the
same way. The cast therefore produced NULL on every row, the inner join to
enrollments matched nothing, and the extract returned zero rows while Amplify
held a full set of results.

Nothing failed. There was no test on the model, and no lineage edge to the
tables it actually read, so neither dbt nor Dagster had any way to notice.

Two changes fixed it. The immediate one repointed the column. The structural one
repointed the model at `int_amplify__mclass__benchmark_student_summary`, so the
raw datasets are now read once, in one place, with real lineage behind them. A
uniqueness test and PII tags landed alongside.

The lesson worth keeping: an extract with no test and no lineage can go to zero
without anyone finding out, and a submission deadline is a poor time to discover
it.

## A second submission route exists, and is not decided

NJDOE now offers direct vendor submission. Starting with the 2026-2027
Beginning-of-Year window, an assessment vendor can submit universal literacy
screener data straight to the state on a district's behalf. It requires an
addendum to the district's contract with the vendor, and NJDOE asks districts to
review any addendum with legal counsel before signing. The vendor then uploads
through a secure file transfer.

For KTAF the vendor would be Amplify — the same source this model already reads.
The precedent is the KIPP Foundation, which already receives Amplify and i-Ready
data directly.

NJDOE states these submission deadlines for the direct route:

| Reporting period  | Due              |
| ----------------- | ---------------- |
| Beginning-of-Year | 13 November 2026 |
| Middle-of-Year    | 12 February 2027 |
| End-of-Year       | 2 July 2027      |

**Nothing is decided.** No addendum exists and nobody has committed to the
direct route. Whether those deadlines also govern a district that keeps
submitting the data itself is unconfirmed — NJDOE states them inside the
direct-submission section.

This is recorded here deliberately. If KTAF hands the job to Amplify and this
extract is retired, a future reader should be able to see that KTAF built and
ran its own screener submission first, and why it stopped, rather than finding a
disabled model with no explanation.
