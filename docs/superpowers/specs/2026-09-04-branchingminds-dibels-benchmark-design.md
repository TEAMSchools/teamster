# Branching Minds DIBELS 8th Benchmark nightly feed

Refs #5143. Follow-up to #4990.

## Context

Branching Minds ingests assessment files nightly from fixed paths on their SFTP
server. A file dropped at `incoming_files/assessments/dibels/benchmark` that
matches the mCLASS export format loads without further action.

Today someone exports DIBELS 8th benchmark results from Amplify by hand and
uploads them. This design replaces that with a nightly automated drop.

Two constraints shape everything below.

**Reporting consistency is the governing requirement.** Whatever reaches
Branching Minds must agree with our dashboards and student reports. Stakeholders
made deliberate decisions about which assessment records count, and those
decisions live in `int_amplify__all_assessments`. This feed inherits them rather
than re-deriving them.

**DIBELS covers Newark and Paterson only.** Camden has no Amplify integration,
so this feed cannot match the three-region coverage of the six models in #4990.

## Goals

- One nightly CSV at `incoming_files/assessments/dibels/benchmark`, current
  academic year, Newark and Paterson.
- Row set identical to what the dashboards show for the same window.
- Column layout matching the mCLASS export sample supplied by Branching Minds.

## Non-goals

- Progress Monitoring. Separate follow-up; we already ingest `dibels8_PM_*.csv`
  for both regions, so the pattern here should carry over.
- Delivery for the other six Branching Minds feeds from #4990. Those models are
  still unmerged and carry their own open questions.
- Backfilling prior academic years.

## Design

### Model

New model at
`src/dbt/kipptaf/models/extracts/branchingminds/rpt_branchingminds__dibels_benchmark.sql`,
materialized into `kipptaf_extracts` alongside the other Branching Minds models.

**Spine.** `int_amplify__all_assessments`, filtered to:

```sql
where assessment_type = 'Benchmark'
  and academic_year = {{ var("current_academic_year") }}
  and region in ('Newark', 'Paterson')
```

That model already applies the `int_google_sheets__dibels_expected_assessments`
gate, the `enrollment_grade = assessment_grade` rule, and the `rn_highest = 1`
dedupe. Those filters are the reporting contract. Do not bypass or reimplement
them.

**Pivot.** `int_amplify__all_assessments` stores one row per measure. Pivot it
back to one row per student per benchmark window:

```sql
pivot (
    max(measure_standard_level) as level,
    max(measure_standard_score) as score,
    max(measure_percentile) as national_norm_percentile,
    max(measure_semester_growth) as semester_growth,
    max(measure_year_growth) as year_growth
    for measure_standard in (
        'Composite' as composite,
        'Letter Names (LNF)' as letter_names_lnf,
        'Phonemic Awareness (PSF)' as phonemic_awareness_psf,
        'Letter Sounds (NWF-CLS)' as letter_sounds_nwf_cls,
        'Decoding (NWF-WRC)' as decoding_nwf_wrc,
        'Word Reading (WRF)' as word_reading_wrf,
        'Reading Accuracy (ORF-Accu)' as reading_accuracy_orf_accu,
        'Reading Fluency (ORF)' as reading_fluency_orf,
        'Reading Comprehension (Maze)' as reading_comprehension_maze
    )
)
```

Aliases in the `in` list are required. Measure names like `Letter Names (LNF)`
are not legal identifier suffixes.

**The pivot input must be an explicit column list.** BigQuery's `pivot`
implicitly groups by every column not named in the pivot or value list.
`int_amplify__all_assessments` carries `round_number`, `month_round`,
`boy_probe_eligible`, `actual_row_count` and others that would shatter the
grain. Select only these before pivoting:

```sql
select
    academic_year,
    region,
    student_number,
    assessment_grade,
    period,
    client_date,
    sync_date,
    measure_standard,
    measure_standard_level,
    measure_standard_score,
    measure_percentile,
    measure_semester_growth,
    measure_year_growth,
from {{ ref("int_amplify__all_assessments") }}
```

**Enrichment.** Left join `int_amplify__mclass__benchmark_student_summary` for
the 58 columns the spine does not carry: student and school identity, teacher
and class, completion status, demographics, and the measures outside the unpivot
set.

`int_amplify__all_assessments` does not emit `surrogate_key` — it is used
internally for the `max_score` window but is absent from the final select. Join
on the natural grain instead:

```sql
left join {{ ref("int_amplify__mclass__benchmark_student_summary") }} as bss
    on spine.student_number = bss.student_primary_id
    and spine.academic_year = bss.academic_year
    and spine.period = bss.benchmark_period
    and spine.assessment_grade = bss.assessment_grade
```

Left join, not inner. A student present in the spine must never disappear
because enrichment missed.

**Grain.** One row per student per benchmark period. Test `unique` on the
combination of `student_number` and `benchmark_period`, plus `not_null` on both.

### Column mapping

Headers stay snake_case in BigQuery. The vendor's human-readable headers are
applied at write time via `file_config.format.header_replacements`, which
`src/teamster/libraries/extracts/assets.py` already supports and
`rpt_clever__students` already uses. That keeps the warehouse table queryable
and testable while the delivered file matches the vendor layout.

Source counts across the 117 columns: 50 from the pivoted spine, 58 from the
enrichment join, 8 empty, 1 needing a decision.

Three renames the int model applies on its way out of staging, easy to miss:

- `basic_comprehension_maze_*` becomes `reading_comprehension_maze_*`
- `composite_score_lexile` becomes `dibels_composite_score_lexile`
- `enrollment_teacher_name` and `enrollment_teacher_staff_id` become
  `official_teacher_name` and `official_teacher_staff_id`, each a coalesce that
  prefers the enrollment value

| #   | Output header                                            | Source                    | Expression                                                        |
| --- | -------------------------------------------------------- | ------------------------- | ----------------------------------------------------------------- |
| 1   | `School Year`                                            | all_assessments           | `concat(academic_year, '-', academic_year + 1)`                   |
| 2   | `State`                                                  | benchmark_student_summary | `state`                                                           |
| 3   | `Multi-District Organization Name`                       | benchmark_student_summary | `multi_district_organization_name`                                |
| 4   | `Reporting Group Name`                                   | benchmark_student_summary | `reporting_group_name`                                            |
| 5   | `District Name`                                          | benchmark_student_summary | `district_name`                                                   |
| 6   | `District Primary ID`                                    | benchmark_student_summary | `district_primary_id`                                             |
| 7   | `School Name`                                            | benchmark_student_summary | `school_name`                                                     |
| 8   | `School Primary ID`                                      | benchmark_student_summary | `school_primary_id`                                               |
| 9   | `Student Last Name`                                      | benchmark_student_summary | `student_last_name`                                               |
| 10  | `Student First Name`                                     | benchmark_student_summary | `student_first_name`                                              |
| 11  | `Student Primary ID (Primary Student ID (State ID))`     | DECIDE                    | `student_number` (see open question 1)                            |
| 12  | `Enrollment Teacher Name`                                | benchmark_student_summary | `official_teacher_name`                                           |
| 13  | `Enrollment Teacher Staff ID`                            | benchmark_student_summary | `official_teacher_staff_id`                                       |
| 14  | `Enrollment Class Name`                                  | benchmark_student_summary | `enrollment_class_name`                                           |
| 15  | `Enrollment Class ID`                                    | benchmark_student_summary | `enrollment_class_id`                                             |
| 16  | `Enrollment Grade`                                       | benchmark_student_summary | `enrollment_grade`                                                |
| 17  | `Assessing Teacher Name`                                 | benchmark_student_summary | `assessing_teacher_name`                                          |
| 18  | `Assessing Teacher Staff ID`                             | benchmark_student_summary | `assessing_teacher_staff_id`                                      |
| 19  | `Assessment Class Name`                                  | benchmark_student_summary | `assessment_class_name`                                           |
| 20  | `Assessment Class ID`                                    | benchmark_student_summary | `assessment_class_id`                                             |
| 21  | `Assessment`                                             | benchmark_student_summary | `assessment`                                                      |
| 22  | `Assessment Edition`                                     | benchmark_student_summary | `assessment_edition`                                              |
| 23  | `Assessment Grade`                                       | all_assessments           | `assessment_grade`                                                |
| 24  | `Benchmark Period`                                       | all_assessments           | `period`                                                          |
| 25  | `Completion Status`                                      | benchmark_student_summary | `completion_status`                                               |
| 26  | `Device Date`                                            | all_assessments           | `client_date`                                                     |
| 27  | `Sync Date`                                              | all_assessments           | `sync_date`                                                       |
| 28  | `Composite Level`                                        | all_assessments           | pivot `Composite` -> `measure_standard_level`                     |
| 29  | `Composite Score`                                        | all_assessments           | pivot `Composite` -> `measure_standard_score`                     |
| 30  | `Composite Score - Lexile`                               | benchmark_student_summary | `dibels_composite_score_lexile`                                   |
| 31  | `Composite - Local Percentile`                           | benchmark_student_summary | `composite_local_percentile`                                      |
| 32  | `Composite - National Norm Percentile`                   | all_assessments           | pivot `Composite` -> `measure_percentile`                         |
| 33  | `Composite - Semester Growth`                            | all_assessments           | pivot `Composite` -> `measure_semester_growth`                    |
| 34  | `Composite - Year Growth`                                | all_assessments           | pivot `Composite` -> `measure_year_growth`                        |
| 35  | `Letter Names (LNF) - Level`                             | all_assessments           | pivot `Letter Names (LNF)` -> `measure_standard_level`            |
| 36  | `Letter Names (LNF) - Score`                             | all_assessments           | pivot `Letter Names (LNF)` -> `measure_standard_score`            |
| 37  | `Letter Names (LNF) - Local Percentile`                  | benchmark_student_summary | `letter_names_lnf_local_percentile`                               |
| 38  | `Letter Names (LNF) - National Norm Percentile`          | all_assessments           | pivot `Letter Names (LNF)` -> `measure_percentile`                |
| 39  | `Letter Names (LNF) - Semester Growth`                   | all_assessments           | pivot `Letter Names (LNF)` -> `measure_semester_growth`           |
| 40  | `Letter Names (LNF) - Year Growth`                       | all_assessments           | pivot `Letter Names (LNF)` -> `measure_year_growth`               |
| 41  | `Phonemic Awareness (PSF) - Level`                       | all_assessments           | pivot `Phonemic Awareness (PSF)` -> `measure_standard_level`      |
| 42  | `Phonemic Awareness (PSF) - Score`                       | all_assessments           | pivot `Phonemic Awareness (PSF)` -> `measure_standard_score`      |
| 43  | `Phonemic Awareness (PSF) - Local Percentile`            | benchmark_student_summary | `phonemic_awareness_psf_local_percentile`                         |
| 44  | `Phonemic Awareness (PSF) - National Norm Percentile`    | all_assessments           | pivot `Phonemic Awareness (PSF)` -> `measure_percentile`          |
| 45  | `Phonemic Awareness (PSF) - Semester Growth`             | all_assessments           | pivot `Phonemic Awareness (PSF)` -> `measure_semester_growth`     |
| 46  | `Phonemic Awareness (PSF) - Year Growth`                 | all_assessments           | pivot `Phonemic Awareness (PSF)` -> `measure_year_growth`         |
| 47  | `Letter Sounds (NWF-CLS) - Level`                        | all_assessments           | pivot `Letter Sounds (NWF-CLS)` -> `measure_standard_level`       |
| 48  | `Letter Sounds (NWF-CLS) - Score`                        | all_assessments           | pivot `Letter Sounds (NWF-CLS)` -> `measure_standard_score`       |
| 49  | `Letter Sounds (NWF-CLS) - Local Percentile`             | benchmark_student_summary | `letter_sounds_nwf_cls_local_percentile`                          |
| 50  | `Letter Sounds (NWF-CLS) - National Norm Percentile`     | all_assessments           | pivot `Letter Sounds (NWF-CLS)` -> `measure_percentile`           |
| 51  | `Letter Sounds (NWF-CLS) - Semester Growth`              | all_assessments           | pivot `Letter Sounds (NWF-CLS)` -> `measure_semester_growth`      |
| 52  | `Letter Sounds (NWF-CLS) - Year Growth`                  | all_assessments           | pivot `Letter Sounds (NWF-CLS)` -> `measure_year_growth`          |
| 53  | `Decoding (NWF-WRC) - Level`                             | all_assessments           | pivot `Decoding (NWF-WRC)` -> `measure_standard_level`            |
| 54  | `Decoding (NWF-WRC) - Score`                             | all_assessments           | pivot `Decoding (NWF-WRC)` -> `measure_standard_score`            |
| 55  | `Decoding (NWF-WRC) - Local Percentile`                  | benchmark_student_summary | `decoding_nwf_wrc_local_percentile`                               |
| 56  | `Decoding (NWF-WRC) - National Norm Percentile`          | all_assessments           | pivot `Decoding (NWF-WRC)` -> `measure_percentile`                |
| 57  | `Decoding (NWF-WRC) - Semester Growth`                   | all_assessments           | pivot `Decoding (NWF-WRC)` -> `measure_semester_growth`           |
| 58  | `Decoding (NWF-WRC) - Year Growth`                       | all_assessments           | pivot `Decoding (NWF-WRC)` -> `measure_year_growth`               |
| 59  | `Word Reading (WRF) - Level`                             | all_assessments           | pivot `Word Reading (WRF)` -> `measure_standard_level`            |
| 60  | `Word Reading (WRF) - Score`                             | all_assessments           | pivot `Word Reading (WRF)` -> `measure_standard_score`            |
| 61  | `Word Reading (WRF) - Local Percentile`                  | benchmark_student_summary | `word_reading_wrf_local_percentile`                               |
| 62  | `Word Reading (WRF) - National Norm Percentile`          | all_assessments           | pivot `Word Reading (WRF)` -> `measure_percentile`                |
| 63  | `Word Reading (WRF) - Semester Growth`                   | all_assessments           | pivot `Word Reading (WRF)` -> `measure_semester_growth`           |
| 64  | `Word Reading (WRF) - Year Growth`                       | all_assessments           | pivot `Word Reading (WRF)` -> `measure_year_growth`               |
| 65  | `Reading Accuracy (ORF-Accu) - Level`                    | all_assessments           | pivot `Reading Accuracy (ORF-Accu)` -> `measure_standard_level`   |
| 66  | `Reading Accuracy (ORF-Accu) - Score`                    | all_assessments           | pivot `Reading Accuracy (ORF-Accu)` -> `measure_standard_score`   |
| 67  | `Reading Accuracy (ORF-Accu) - Local Percentile`         | benchmark_student_summary | `reading_accuracy_orf_accu_local_percentile`                      |
| 68  | `Reading Accuracy (ORF-Accu) - National Norm Percentile` | all_assessments           | pivot `Reading Accuracy (ORF-Accu)` -> `measure_percentile`       |
| 69  | `Reading Accuracy (ORF-Accu) - Semester Growth`          | all_assessments           | pivot `Reading Accuracy (ORF-Accu)` -> `measure_semester_growth`  |
| 70  | `Reading Accuracy (ORF-Accu) - Year Growth`              | all_assessments           | pivot `Reading Accuracy (ORF-Accu)` -> `measure_year_growth`      |
| 71  | `Reading Fluency (ORF) - Level`                          | all_assessments           | pivot `Reading Fluency (ORF)` -> `measure_standard_level`         |
| 72  | `Reading Fluency (ORF) - Score`                          | all_assessments           | pivot `Reading Fluency (ORF)` -> `measure_standard_score`         |
| 73  | `Reading Fluency (ORF) - Local Percentile`               | benchmark_student_summary | `reading_fluency_orf_local_percentile`                            |
| 74  | `Reading Fluency (ORF) - National Norm Percentile`       | all_assessments           | pivot `Reading Fluency (ORF)` -> `measure_percentile`             |
| 75  | `Reading Fluency (ORF) - Semester Growth`                | all_assessments           | pivot `Reading Fluency (ORF)` -> `measure_semester_growth`        |
| 76  | `Reading Fluency (ORF) - Year Growth`                    | all_assessments           | pivot `Reading Fluency (ORF)` -> `measure_year_growth`            |
| 77  | `Error Rate (ORF) - Score`                               | benchmark_student_summary | `error_rate_orf_score`                                            |
| 78  | `Basic Comprehension (Maze) - Level`                     | all_assessments           | pivot `Reading Comprehension (Maze)` -> `measure_standard_level`  |
| 79  | `Basic Comprehension (Maze) - Score`                     | all_assessments           | pivot `Reading Comprehension (Maze)` -> `measure_standard_score`  |
| 80  | `Basic Comprehension (Maze) - Local Percentile`          | benchmark_student_summary | `reading_comprehension_maze_local_percentile`                     |
| 81  | `Basic Comprehension (Maze) - National Norm Percentile`  | all_assessments           | pivot `Reading Comprehension (Maze)` -> `measure_percentile`      |
| 82  | `Basic Comprehension (Maze) - Semester Growth`           | all_assessments           | pivot `Reading Comprehension (Maze)` -> `measure_semester_growth` |
| 83  | `Basic Comprehension (Maze) - Year Growth`               | all_assessments           | pivot `Reading Comprehension (Maze)` -> `measure_year_growth`     |
| 84  | `Correct Responses (Maze) - Score`                       | benchmark_student_summary | `correct_responses_maze_score`                                    |
| 85  | `Incorrect Responses (Maze) - Score`                     | benchmark_student_summary | `incorrect_responses_maze_score`                                  |
| 86  | `Vocabulary - Level`                                     | benchmark_student_summary | `vocabulary_level`                                                |
| 87  | `Vocabulary - Score`                                     | benchmark_student_summary | `vocabulary_score`                                                |
| 88  | `Spelling - Level`                                       | benchmark_student_summary | `spelling_level`                                                  |
| 89  | `Spelling - Score`                                       | benchmark_student_summary | `spelling_score`                                                  |
| 90  | `RAN - Level`                                            | benchmark_student_summary | `ran_level`                                                       |
| 91  | `RAN - Score`                                            | benchmark_student_summary | `ran_score`                                                       |
| 92  | `Risk Indicator - Level`                                 | benchmark_student_summary | `risk_indicator_level`                                            |
| 93  | `Oral Language - Level`                                  | benchmark_student_summary | `oral_language_level`                                             |
| 94  | `Oral Language - Score`                                  | benchmark_student_summary | `oral_language_score`                                             |
| 95  | `Date of Birth`                                          | benchmark_student_summary | `date_of_birth`                                                   |
| 96  | `Gender`                                                 | benchmark_student_summary | `gender`                                                          |
| 97  | `Race`                                                   | benchmark_student_summary | `race`                                                            |
| 98  | `Hispanic or Latino Ethnicity`                           | benchmark_student_summary | `hispanic_or_latino_ethnicity`                                    |
| 99  | `Special Education`                                      | benchmark_student_summary | `special_education`                                               |
| 100 | `Disability`                                             | benchmark_student_summary | `disability`                                                      |
| 101 | `Specific Disability`                                    | benchmark_student_summary | `specific_disability`                                             |
| 102 | `Section 504`                                            | benchmark_student_summary | `section_504`                                                     |
| 103 | `IEP Status`                                             | benchmark_student_summary | `iep_status`                                                      |
| 104 | `Economically Disadvantaged`                             | benchmark_student_summary | `economically_disadvantaged`                                      |
| 105 | `Meal Status`                                            | benchmark_student_summary | `meal_status`                                                     |
| 106 | `Title I`                                                | benchmark_student_summary | `title_i`                                                         |
| 107 | `Migrant`                                                | benchmark_student_summary | `migrant`                                                         |
| 108 | `ELL Status`                                             | benchmark_student_summary | `ell_status`                                                      |
| 109 | `Home Language`                                          | benchmark_student_summary | `home_language`                                                   |
| 110 | `DPI Course Code`                                        | empty                     | not in our feed (see open question 2)                             |
| 111 | `Reading Retained`                                       | empty                     | not in our feed (see open question 2)                             |
| 112 | `birthdate`                                              | empty                     | not in our feed (see open question 2)                             |
| 113 | `clDcid`                                                 | empty                     | not in our feed (see open question 2)                             |
| 114 | `clSourcedId`                                            | empty                     | not in our feed (see open question 2)                             |
| 115 | `homeroom`                                               | empty                     | not in our feed (see open question 2)                             |
| 116 | `readingRetained`                                        | empty                     | not in our feed (see open question 2)                             |
| 117 | `sex`                                                    | empty                     | not in our feed (see open question 2)                             |

### Delivery

New SSH resource in `src/teamster/code_locations/kipptaf/resources.py`,
following the `LATTICE` and `LITTLESIS` shape — host, port 22, username, and
password read from the standard four settings:

```python
SSH_RESOURCE_BRANCHING_MINDS = SSHResource(
    remote_host=EnvVar("BRANCHINGMINDS_SFTP_HOST"),
    remote_port=22,
    username=EnvVar("BRANCHINGMINDS_SFTP_USERNAME"),
    password=EnvVar("BRANCHINGMINDS_SFTP_PASSWORD"),
)
```

Registered as `ssh_branchingminds` in the resource dict in
`src/teamster/code_locations/kipptaf/definitions.py`. The account is already
provisioned; the secret still needs wiring.

New config at
`src/teamster/code_locations/kipptaf/extracts/config/branchingminds.yaml`:

```yaml
assets:
  - query_config:
      type: schema
      value:
        table:
          name: rpt_branchingminds__dibels_benchmark
          schema: kipptaf_extracts
    file_config:
      stem: dibels8_benchmark_{today}
      suffix: csv
      format:
        header_replacements:
          school_year: School Year
          # ... 116 more
```

Use the `type: schema` query form. It is the only form that gets the
`zz_dagster_` branch-deploy redirect, so a branch deployment cannot write to the
live vendor path. Keep `destination_config.path` relative
(`incoming_files/assessments/dibels/benchmark`), per the extracts library's own
guidance about server-side prefix changes.

Then an asset built by `build_bigquery_query_sftp_asset` in
`extracts/assets.py`, a job in `extracts/jobs.py`, and a `0 3 * * *` schedule in
`extracts/schedules.py`, matching the existing nightly extract cluster.

The `{today}` stem means nightly drops never overwrite each other. The Export
Guide's `[Testing Window] DIBELS 8th` naming applies to manual uploads only.

### Personal information

This file is dense with student personal information by design — names, date of
birth, student ID, and the IEP, 504, disability, meal status, and English
learner fields. That is legitimate for a contracted vendor, and Branching Minds
needs the identity columns to match students on their side.

The model YAML needs `config.meta.contains_pii: true` on every identity and
demographic column. Validation output stays local; no row-level values go into
pull request comments, issues, or any external surface.

### Testing

- `unique` and `not_null` on the grain columns.
- `dbt build --select rpt_branchingminds__dibels_benchmark+` from the worktree.
- Compare row counts against the dashboards for the same window. Agreement is
  the acceptance criterion, not a sanity check.
- Confirm the written header row matches the vendor sample column for column.
- Run the asset in a branch deployment and confirm it writes to the redirected
  schema rather than the vendor path.

## Open questions

These need answers from Branching Minds before the feed goes live. None blocks
building the model.

**1. Which student identifier should `Student Primary ID` carry?** The sample
header reads `Student Primary ID (Primary Student ID (State ID))`, implying a
state ID. Our staging model drops the state ID variant entirely — it selects
`cast(student_primary_id_studentnumber as int) as student_primary_id`, so the
only identifier surviving downstream is the PowerSchool student number. If
Branching Minds matches on state ID, this feed cannot supply it without a
staging change.

**2. Our export variant differs from the sample.** The sample file and the file
Amplify drops on our SFTP are different variants of the mCLASS export. Nine
columns differ in each direction. The sample has eight trailing PowerSchool-sync
columns we do not receive: `DPI Course Code`, `Reading Retained`, `birthdate`,
`clDcid`, `clSourcedId`, `homeroom`, `readingRetained`, and `sex`. Our feed
carries teacher-number and secondary or additional student ID variants the
sample lacks. The design emits the sample's layout with those eight empty.
Confirm Branching Minds tolerates empty values there rather than rejecting the
file.

**3. Should the non-dashboard measures be sent?** Vocabulary, Spelling, RAN,
Oral Language, Risk Indicator, Error Rate, Maze response counts, local
percentiles, and composite Lexile are absent from the unpivot, so they play no
part in our dashboards — but they do exist in
`int_amplify__mclass__benchmark_student_summary` and the design currently
sources them from there. The row set stays governed by the spine either way, so
this is a column-level judgment: send real source values that our reporting does
not surface, or leave them empty for strict parity. Recommend sending them,
since omitting data the vendor expects is the larger gap, but this is a
stakeholder call given the consistency requirement.

**4. `District Primary ID`.** The six models in #4990 use KTAF-assigned
Branching Minds district codes (Newark `7325`, Paterson `7899`). The mCLASS
export carries its own `district_primary_id`. The design passes through the
mCLASS value, since this file lands on the DIBELS path where the mCLASS format
is expected. Worth one sentence to the Branching Minds contact to confirm they
key on the same value across both feeds.

## Prerequisites

- Branching Minds SFTP secret wired for the `kipptaf` code location.
- This branch stacks on `baribradley/feat/branchingminds-extracts`, so #4990
  merges first. A non-`main` base skips `claude-review`; dbt Cloud CI still
  runs, since it is not base-gated.
