# Quill Pilot Demographics Extract — Design

Refs #4848

## Context

A signed Data Sharing Agreement (2026-02-13) covers the SY25-26 Quill.org pilot
with an external research partner. The partner holds platform telemetry for the
pilot roster and needs student demographics to use as covariates in a pre- and
post-period analysis. Due Friday 2026-08-14.

Requested fields: race, gender, free or reduced meal status, IEP status, MLL
status. The request also said to strip student and teacher identifiers while
"retaining the student ID."

Source packet (local only, not committed): `.claude/scratch/Quill request/` —
the agreement, the request note, and the roster export
(`query_result_2026-04-13`, 269 rows).

## Findings that shaped the design

**The roster's `Studetn ID` column is not a KIPP identifier.** Zero of 248
distinct values match `student_number` in the warehouse. The values are Quill
platform user IDs (7-8 digits, 10.1M-20.1M, higher for accounts created later in
the year). The only usable join key in the roster is student email.

This is fortunate rather than inconvenient. A file keyed only on the Quill ID
carries no KIPP identifier at all, which is what the agreement asks for: a
persistent pseudonymous identifier, with the supplier retaining the
re-identification key and never sharing it. Had the column really held
`student_number`, honoring the request literally would have transmitted a FERPA
direct identifier.

**Match rates** against `int_extracts__student_enrollments`:

| Measure                                      | Count     |
| -------------------------------------------- | --------- |
| Roster rows / distinct students              | 269 / 248 |
| Resolved to SY25-26, grade 8 (Rise, Purpose) | 244       |
| Resolved but last enrolled SY24-25           | 1         |
| Never present under the roster email         | 3         |
| Nulls across the five fields for the 244     | 0         |

**Roster shape.** Nine Quill classrooms taught by two teachers. Twenty-one
students appear in two sections, always two sections of their own teacher, so
the duplication is real roster structure rather than an export artifact. Teacher
maps 1:1 to school (123 students at one, 121 at the other).

## Decisions

| Decision               | Choice                                          | Why                                                                                                                                |
| ---------------------- | ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Join key               | Student email                                   | The only key the roster and the warehouse share                                                                                    |
| Delivered identifier   | Quill platform ID, unchanged                    | Carries no KIPP identifier; the partner already holds it                                                                           |
| Classroom and teacher  | Pseudonymous codes                              | Preserves classroom nesting for the analysis without transmitting staff names                                                      |
| Unmatched students     | Kept, with a source flag                        | The partner can see which rows lack data instead of silently losing four students from their N                                     |
| As-of year             | SY25-26, falling back to most recent prior year | Demographics should describe the pilot year, not today                                                                             |
| Grade level and school | Excluded                                        | Every student is grade 8, and teacher code already separates the schools 1:1 — both add identifiability without adding information |
| Value encoding         | One column per requested field, readable labels | Data minimization: no derived binary duplicates beyond the five fields                                                             |

## Deliverable

One workbook, two sheets, written to a local output directory as
`quill_seta_ed_student_demographics_{extract_date}.xlsx`.

### Sheet `student_demographics`

269 rows, one per student-classroom pair.

| Column                | Values                                                                |
| --------------------- | --------------------------------------------------------------------- |
| `quill_student_id`    | Unchanged from the roster export                                      |
| `classroom_code`      | `C01` through `C09`                                                   |
| `teacher_code`        | `T1`, `T2`                                                            |
| `race_ethnicity`      | Asian, BL-AA, Hispanic or Latino, AI-AN, NH-OPI, 2+ races, White, DTS |
| `gender`              | Female, Male, Non-Binary                                              |
| `meal_status`         | Free, Reduced, Paid                                                   |
| `iep_status`          | Has IEP, No IEP                                                       |
| `mll_status`          | ML, Not ML                                                            |
| `demographics_source` | `SY25-26`, `SY24-25 (fallback)`, `not matched`                        |

Dropped with no replacement: student name, student email, classroom name,
teacher name, teacher email.

### Sheet `data_dictionary`

One row per delivered column: definition, source model and column, value coding,
and known gaps. The agreement requires documentation sufficient for a qualified
third party to reproduce the dataset, so this ships with the file rather than
living only in the repo.

## Derivation

Source: `int_extracts__student_enrollments` filtered to `academic_year = 2025`
and `rn_year = 1`, joined on `lower(student_email)` against the roster email.

Fallback: a student with no SY25-26 row takes their most recent prior
`academic_year` row at `rn_year = 1`, tagged in `demographics_source`. One
student qualifies (last enrolled SY24-25, transferred out).

Label map provenance, corrected after verifying against
`rpt_gsheets__csgf_enrollment`: `race_ethnicity` categories follow csgf, but
punctuation differs — csgf uses slashes (`BL/AA`, `AI/AN`, `NH/OPI`), this
extract uses hyphens (`BL-AA`, `AI-AN`, `NH-OPI`) — so a KTAF analyst comparing
the two outputs will find the strings do not join. `gender` follows
`int_extracts__student_enrollments.aligned_gender`, not csgf, which has no
student gender map at all (only a staff one). The `meal_status`
Free/Reduced/Paid trichotomy is introduced by this extract; csgf only reduces
`lunch_status` to a binary FRL flag, so there is no prior model for the
three-way vocabulary. `iep_status` and `mll_status` pass through the model's
existing labels unchanged. Full codes:

- `race_ethnicity`: `A` Asian, `B` BL-AA, `H` Hispanic or Latino, `I` AI-AN, `P`
  NH-OPI, `T` 2+ races, `W` White, and `M`/`N`/`Y`/anything else DTS
- `gender`: `F` Female, `M` Male, `X` Non-Binary
- `meal_status` from `lunch_status`: `F` and `FDC` Free, `R` Reduced, `P` Paid

Observed value domains for the 244 matched students: race `B`, `T`, `H`, `I`,
`P`; gender `F`, `M`; meal `F`, `R`, `P`. No nulls.

## Pseudonymization and the retained key

Codes are assigned by **order of first appearance in the roster export**, not
alphabetically by name. Alphabetical assignment would be derivable from the
committed script by anyone who knows which teachers taught the sections; row
order is not public.

Stability across the pre- and post-period deliveries comes from the key file: if
one already exists, the script reads the prior assignments and reuses them,
assigning new codes only to classrooms it has not seen.

The key file maps `quill_student_id` to student email, `student_number`,
classroom name, teacher name, and their codes. It is written to
`.claude/scratch/` only. Never committed, never transmitted. This is the
agreement's re-identification key, which the supplier retains and the researcher
never receives.

## Validation gate

The script asserts against its own written output rather than against in-memory
values, so a serialization mistake cannot pass:

1. Row count is 269 and distinct `quill_student_id` count is 248.
1. No cell in the workbook matches a roster name, an email shape, or any
   `student_number` returned by the query.
1. Every row either carries all five demographic values or reads `not matched`
   in `demographics_source`.
1. Cross-tab counts for each demographic field print to the terminal.

Assertion failures abort before the workbook is finalized.

The cross-tab print exists because the counts matter before the file is sent. At
n=244 race has singleton cells (one AI/AN, one NH/OPI) and several cells under
five. With `classroom_code` alongside, a holder of the original roster could
narrow those rows to one student. The default is to ship real categories
uncollapsed: the agreement assigns small-cell suppression to the researcher at
publication, not to the supplier at transfer. Collapsing rare categories into
"Other" remains available if the agreement owner prefers it.

## Repo artifacts

`scripts/extract_quill_seta_ed_demographics.py`

Roster path, output directory, and key-file path are arguments. Nothing about
the roster is hardcoded, following the precedent set by `cube_rls_matrix.py` for
keeping PII out of tracked files. Registered in the `scripts/CLAUDE.md` catalog.

`docs/reference/quill-seta-ed-demographics-extract.md`

Data dictionary, variable-level lineage, inclusion and exclusion rules, and
rerun steps. Added to the Reference section of the MkDocs nav. Names no student
and no staff member, and does not publish which code corresponds to which
classroom, teacher, or school.

## Out of scope

- **Sending the file.** The requester sends it. Nothing in this work transmits
  data outside the repo and the local filesystem.
- **Any warehouse write.** The extract reads only.
- **A dbt model or Dagster asset.** Two deliveries over one study does not
  justify seeding a roster of student emails into git.

## Open items for the requester

- Confirm the five fields are enumerated in Exhibit A of the agreement. Exhibit
  A is referenced but was not included in the packet. If the fields are not
  listed there, this is a scope change requiring written approval from both
  signers rather than just a file.
- Decide whether to collapse the singleton race categories before sending.
- Decide whether the agreement owner reviews the workbook before it leaves.
  Recommended, given the singleton cells.
- Three roster students cannot be resolved at all. If their identities matter to
  the study's N, someone with roster access will need to reconcile them by hand;
  the extract will ship them as `not matched`.
