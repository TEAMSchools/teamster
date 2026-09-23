# NJDOE Universal Screener Data Model

New Jersey requires districts to report universal literacy screener results for
students in grades K through 3. KTAF screens with DIBELS, administered through
Amplify, and `rpt_gsheets__njdoe_universal_screener_data` reshapes those results
into the columns the state's collection expects.

Exposure: `rpt_gsheets__njdoe_universal_screener_data` in
`src/dbt/kipptaf/models/exposures/google-sheets.yml`. The model writes to a
Google Sheet, which a person then submits to NJDOE. Nothing in this pipeline
talks to the state directly.

Grain: one row per student, benchmark period and assessment name, carrying a
score and a performance level for each of six measures. The full composite key
the SQL groups on is `region`, `schoolid`, `school`, `benchmark_period`,
`district_code`, `school_code`, `sid` and `assessment_name`.

`assessment_name` is part of that key and is easy to miss. Amplify has shipped
one assessment edition per year so far, so in practice the grain has been one
row per student per period — but the query does not enforce that, and no
uniqueness test guards it. An edition change mid-year would produce two rows for
the same student and period without anything failing.

!!! danger "The extract currently returns 0 rows"

    Verified against production on 22 September 2026.
    `kipptaf_extracts.rpt_gsheets__njdoe_universal_screener_data` is empty, and
    the cause is upstream rather than a shortage of assessment data — Amplify
    holds 3,078 New Jersey rows in grades K through 3 for AY2026.

    Amplify moved the student identifier between years. The model reads
    `student_primary_id_studentnumber`, which was populated on all 8,150 AY2025
    rows and is populated on **none** of the 3,078 AY2026 rows. The value now
    arrives in `student_primary_id` instead. `additional_student_id_sisid` and
    `secondary_student_id_stateid` moved the same way, to
    `additional_student_id` and to nothing respectively.

    The `safe_cast` on that column therefore returns NULL for every row, the
    inner join to `int_extracts__student_enrollments` matches nothing, and the
    view returns empty. Nothing fails — there is no test on this model, so the
    break is silent.

    The Beginning-of-Year submission is due 13 November 2026.

!!! warning "This model reads raw Amplify datasets, not a dbt source"

    The two source reads are bare dataset paths —
    `kippnewark_amplify.benchmark_student_summary` and
    `kipppaterson_amplify.benchmark_student_summary` — with an inline comment
    saying they are hardcoded to reach raw data. dbt therefore builds no lineage
    edge to the tables this model actually depends on, and Dagster does not know
    the dependency exists. An Amplify column rename breaks this model with no
    graph signal and no upstream test failure. The only `ref()` calls are to
    `int_extracts__student_enrollments` and `int_people__location_crosswalk`.

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
| `composite`            | Amplify composite                            |

Each produces two output columns, a `_score` and a `_level`.

## Performance levels are recoded to the state's vocabulary

NJDOE does not use Amplify's benchmark wording, so the model translates it.

| Amplify level                                | Reported as         |
| -------------------------------------------- | ------------------- |
| Above Benchmark                              | `Above Grade Level` |
| At Benchmark                                 | `At Grade Level`    |
| Below Benchmark **and** Well Below Benchmark | `Below Grade Level` |
| Tested Out                                   | `TO`                |
| Discontinued                                 | `D`                 |

Two consequences worth knowing before anyone reads these numbers as DIBELS
numbers.

**The two below-benchmark levels collapse into one.** Amplify distinguishes
Below Benchmark from Well Below Benchmark; this extract does not. That
distinction is not recoverable from the submitted file, so do not use this model
as a source for internal below-benchmark analysis. Use the DIBELS dashboard
lineage for that.

**A status can arrive in the percentile field rather than the level field.** The
model resolves the level as "if the percentile reads `Tested Out` or
`Discontinued`, use that; otherwise use the level." So a student who tested out
of a measure carries `TO` even though the level column said something else. This
is a quirk of the source, reproduced deliberately.

## Scope

The model is narrow on purpose. Every filter below is deliberate.

- New Jersey only. The Newark branch additionally excludes Florida rows before
  the union, and the joined set is filtered to `state = 'NJ'`. Miami is out of
  scope because Florida runs no equivalent collection.
- Grades K, 1, 2 and 3 only.
- Enrollment grade must equal the grade the student was assessed in. A student
  assessed off-grade is dropped rather than reported at either grade.
- The current academic year only, from `var("current_academic_year")`.
- One enrollment row per student per year, via `rn_year = 1`.

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

!!! question "Two things this page cannot yet answer"

    **Does Camden reach the output?** The union reads only the
    `kippnewark_amplify` and `kipppaterson_amplify` datasets, yet the `CASE`
    statements carry Camden codes. The likely explanation is that
    `kippnewark_amplify` holds all New Jersey regions and `region` is resolved
    downstream from the location crosswalk, which would make this correct. That
    has not been confirmed against production.

    **What does NJDOE expect in `school_code`?** A single hardcoded value per
    region suggests a district-level or LEA-level identifier rather than a
    per-school one. Confirm against the state's specification before trusting
    it.

## Shape of the transformation

Five steps, and the middle three exist only to move measures between rows and
columns.

1. Union the two raw Amplify datasets and cast the school year to an integer
   academic year.
2. Join to the location crosswalk on school name, and to the enrollment extract
   on academic year and student number. Both are inner joins, so a student
   missing from either side is dropped silently.
3. `UNPIVOT` the six measures from columns into rows, so the level recoding can
   be written once instead of six times.
4. Recode the levels.
5. Two `PIVOT`s back into wide columns — one for scores, one for levels — joined
   on the full row key.

The double pivot is why scores and levels are assembled separately and then
rejoined, rather than travelling together.

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

## Known gaps

Neither is a documentation problem, and both are real.

**No uniqueness test.** Repo convention requires one on every `rpt_` model. This
one has no `data_tests` block at all, so nothing guards the student and
benchmark-period grain.

**No PII tagging.** `sid` carries the state student number, a direct identifier,
and every score and level column is student-level assessment content. The model
declares no `config.meta.contains_pii` anywhere. See
`.claude/rules/ferpa-pii.md` before adding tags.
