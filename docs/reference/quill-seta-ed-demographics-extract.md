# Quill Pilot Demographics Extract

This page documents `scripts/extract_quill_seta_ed_demographics.py`, which
builds a de-identified student demographics workbook for KTAF's SY25-26
Quill.org pilot research partner, under a Data Sharing Agreement signed
2026-02-13. The requested fields are race and ethnicity, gender, meal status,
IEP status, and multilingual learner (MLL) status, used as covariates in the
partner's pre- and post-period analysis. The agreement requires "Documentation"
alongside any derived dataset — a data dictionary, variable-level lineage, and
inclusion and exclusion rules sufficient for a qualified third party to
reproduce the dataset. This page is that documentation. Refs #4848.

## Identifiers

The Quill roster export's `Studetn ID` column (the typo is in the platform's own
export header, matched verbatim in the script so a corrected export fails loudly
instead of silently) holds a Quill platform user ID. It is **not** a KIPP
`student_number` — none of the roster's distinct students matched a
`student_number` in the warehouse.

The only field the roster and the warehouse share is student email, so the join
runs on `lower(student_email)`. Because the delivered identifier is the roster's
own Quill ID, unchanged, the workbook the partner receives carries no KIPP
identifier at all — no name, no `student_number`, no state or local ID.

## Data Dictionary

This table is transcribed by hand from the `DATA_DICTIONARY` constant in the
script. Only the `data_dictionary` sheet shipped inside the workbook is
generated from that constant — this table is not, and it has already drifted out
of sync with the constant once. Re-check this table against `DATA_DICTIONARY`
whenever the constant changes.

| column                | definition                                                                | source                                             | coding                                                                                                                                                                                         |
| --------------------- | ------------------------------------------------------------------------- | -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `quill_student_id`    | Quill platform user ID for the student, unchanged from the roster export. | Quill roster export, column `Studetn ID`           | Integer. Join key to Quill platform data. Not a school district identifier.                                                                                                                    |
| `classroom_code`      | Pseudonymous code for the Quill classroom section.                        | Assigned by this script                            | `C01` through `C09`. Mapping to section names is retained by the data supplier.                                                                                                                |
| `teacher_code`        | Pseudonymous code for the teacher of record for the section.              | Assigned by this script                            | `T1`, `T2`. Maps 1:1 to school. Mapping to names is retained by the data supplier.                                                                                                             |
| `race_ethnicity`      | Race and ethnicity as recorded in the student information system.         | `int_extracts__student_enrollments.race_ethnicity` | Asian, BL-AA, Hispanic or Latino, AI-AN, NH-OPI, 2+ races, White, DTS. DTS means declined to state. Blank when the student was not matched.                                                    |
| `gender`              | Gender as recorded in the student information system.                     | `int_extracts__student_enrollments.gender`         | Female, Male, Non-Binary. Blank when the student was not matched.                                                                                                                              |
| `meal_status`         | National School Lunch Program eligibility for the school year.            | `int_extracts__student_enrollments.lunch_status`   | Free, Reduced, Paid. Direct certification is reported as Free. Blank when the student was not matched.                                                                                         |
| `iep_status`          | Whether the student had an active individualized education program.       | `int_extracts__student_enrollments.iep_status`     | Has IEP, No IEP. Blank when the student was not matched.                                                                                                                                       |
| `mll_status`          | Multilingual learner status.                                              | `int_extracts__student_enrollments.ml_status`      | ML, Not ML. Blank when the student was not matched.                                                                                                                                            |
| `demographics_source` | Which school year's enrollment record supplied this row's values.         | Assigned by this script                            | `SY25-26` for the pilot year. `SYxx-yy (fallback)` when the student was not enrolled in the pilot year and an earlier year was used. `not matched` when no enrollment record was found at all. |

Dropped with no replacement: student name, student email, teacher email.
Classroom name and teacher name are not dropped outright — they are replaced by
`classroom_code` and `teacher_code` above.

## Lineage

Source: `teamster-332318.kipptaf_extracts.int_extracts__student_enrollments`,
filtered to `academic_year = 2025` (the SY25-26 pilot year) and `rn_year = 1` (a
student's primary enrollment stint within the year, so a mid-year school move
does not produce two rows for one student-year). Joined to the roster on
`lower(student_email)`.

Label map provenance is mixed, not a single reused convention. `race_ethnicity`
categories follow `rpt_gsheets__csgf_enrollment`, but this extract's punctuation
differs from it — csgf emits `BL/AA`, `AI/AN`, `NH/OPI` with slashes, while this
script emits `BL-AA`, `AI-AN`, `NH-OPI` with hyphens, so a KTAF analyst
comparing the two outputs will find the strings do not join. `gender` follows
`int_extracts__student_enrollments.aligned_gender`, not csgf — csgf has no
student gender map at all, only a staff one. `meal_status` (sourced from
`lunch_status`)'s Free/Reduced/Paid trichotomy is introduced by this extract;
csgf only reduces `lunch_status` to a binary FRL flag, so no prior model carries
the three-way vocabulary. `iep_status` and `mll_status` (sourced from
`ml_status`) pass the model's existing labels through unchanged.

## Inclusion and Exclusion Rules

- **Grain**: one row per student-classroom pair, not per student. A student
  enrolled in two Quill sections appears twice in the delivered sheet, with the
  same demographics repeated on both rows.
- **Fallback**: a student with no pilot-year (`academic_year = 2025`) enrollment
  record falls back to their most recent prior year, and `demographics_source`
  records which year supplied the row.
- **Unmatched**: a student with no enrollment record under the roster's email at
  all ships with blank demographic fields and `demographics_source` set to
  `not matched`, rather than being dropped from the sheet.
- **Grade level and school are excluded** from the delivered columns. Every
  student in the pilot is grade 8, and `teacher_code` already separates the two
  schools 1:1 — both fields would add identifiability without adding information
  the partner can use.

Across the roster's 269 rows (248 distinct students), 245 resolved to a
warehouse enrollment record and 3 did not.

## Rerun Steps

The script carries a PEP 723 inline dependency header, so a plain `uv run`
installs `openpyxl` and `google-cloud-bigquery` at launch — no `--with` flag
needed:

```bash
uv run scripts/extract_quill_seta_ed_demographics.py \
  --roster "{path to roster .xlsx}" \
  --output-dir "{path to output directory}" \
  --key-file "{path to retained re-identification key file}"
```

`--pilot-year` defaults to `2025` and `--gcp-project` defaults to
`teamster-332318`; pass either explicitly to override. The roster path is never
committed and never appears in this repo — pass the actual export path at the
terminal.

Running the test suite is different: `pytest` loads the script through
`importlib`, which does not evaluate PEP 723 headers, so the tests still need
the dependency spelled out on the command line:

```bash
uv run --with openpyxl pytest tests/test_extract_quill_seta_ed_demographics.py
```

## Handling of the Retained Key

The `--key-file` argument points at a local, gitignored JSON file (for example,
a path under `.claude/scratch/`) that maps each `quill_student_id` to the
student's email, `student_number`, classroom name, teacher name, and their
assigned `classroom_code` / `teacher_code`. This is the re-identification key
the data sharing agreement requires the supplier to retain — it is never
committed and never transmitted to the research partner.

On rerun, if a key file already exists at the given path, the script reads the
prior classroom and teacher code assignments and reuses them, assigning new
codes only to classrooms or teachers it has not seen before. This keeps
`classroom_code` and `teacher_code` stable across the pilot's pre- and
post-period deliveries, which the partner needs in order to link records between
the two files.
