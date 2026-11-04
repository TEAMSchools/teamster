# IGNITE R2I Evaluation Extract (Mathematica) — Design

## Context

KIPP NJ participates in the IGNITE Network evaluation of Marshall Street's
research-to-impact (R2I) practices, conducted by Mathematica for the Gates
Foundation. The work is governed by Memorandum of Understanding and Data Sharing
Agreement 52283A001 between Mathematica, Marshall Street (a division of Summit
Public Schools), New Jersey Children's Foundation as intermediary, and KIPP NJ.
It was signed by KIPP NJ's COO on 2025-02-15 and countersigned 2025-03-07.

Two clauses shape every decision here:

- **Section 1.9** obligates KIPP NJ to provide **deidentified** data. This is
  the contractual basis for the share, not a courtesy.
- **Section 1.10** establishes the legal authority as FERPA's legitimate
  educational interest provision (34 CFR 99).

The agreement runs through completion of the evaluation, anticipated around
2026-12-31. Mathematica has stated it **cannot incorporate any data received
after 2026-10-15**.

Two Newark high schools are treatment sites: Newark Lab HS and Newark Collegiate
Academy. Each has a designated IGNITE site lead (both Assistant Principals of
Special Education), consistent with a study centered on students with
disabilities. Three practices are under study:

| Code  | Practice            |
| ----- | ------------------- |
| `cp`  | Co-planning         |
| `rdc` | Routine data cycles |
| `rr`  | Repeated reading    |

The submission is overdue. It was contractually due within three weeks of the
2025-2026 school year ending.

## Goals

1. Durable, re-runnable dbt models that emit Mathematica's exact column names,
   so the October phase-2 submission and any revision rounds cost nothing to
   regenerate.
2. Deidentified by construction — no student or state identifier can reach an
   outbound model.
3. Structurally complete before the treatment-assignment file arrives, so the
   missing input blocks six columns rather than the whole extract.

## Non-goals

- Automating assembly into Mathematica's workbook or the Box upload. Both stay
  manual; the volume is one workbook per phase.
- The study's other data collection (educator interviews, surveys, classroom
  observations). Mathematica gathers those directly from schools.
- Writing to Box from Dagster. No credentials exist and none are warranted for a
  twice-yearly manual upload.

## Deliverables

Four files across two phases, covering grades 9-12 for academic years 2025
and 2026.

| File                               | Grain                          | Phase |
| ---------------------------------- | ------------------------------ | ----- |
| Student-level data (their Table 1) | one row per student per year   | 1     |
| Course-level data (their Table 2)  | one row per student per course | 1     |
| Teacher and Course Identification  | one row per treated class      | 1     |
| 2025-2026 state assessment         | one row per student            | 2     |

The phase-2 file is a column subset of Table 1, delivered on its own sheet
rather than as a new structure.

Phase 1 carries 2024-2025 state assessment results in the main student sheet.
Phase 2 delivers 2025-2026 results on a separate sheet and must land before
2026-10-15. Those results landed on 2026-09-30, so phase 2 is no longer waiting
on the state.

Course-level data is restricted to English, Math, Science, and History classes.

Note a contradiction in the source memo: Section C describes the student-level
file as carrying "state assessment data from 2024-2025" while Table 1 lists
`school_year` values of 2025 and 2026. The template workbook resolves it — its
`Student Data` sheet labels the assessment block `2024-2025 State Assessment`
and carries a separate `25_26 State Assessment Data` sheet. The two-phase
reading above is correct.

## Approach

Build a self-contained model directory whose outbound models already speak
Mathematica's vocabulary, and isolate the one missing input behind a single
seam.

The memo specifies treatment flags as `1` for treated students, `else = 0`.
Every column in both tables can therefore be built, tested, and reviewed before
the site-lead file exists. What the missing file withholds is not structure — it
is only the `1`s.

Precedent for an outbound funder share of this shape:
`rpt_gsheets__csgf_hs_enrollment`.

## Components

New directory `src/dbt/kipptaf/models/extracts/ignite/`.

As built (2026-09-16). Intermediates sit under `intermediate/`; the whole tree
inherits `contract: enforced: true` and the `extracts` schema from
`dbt_project.yml`.

| Node                               | Purpose                                                            |
| ---------------------------------- | ------------------------------------------------------------------ |
| `seed_ignite__treatment_sections`  | 18 treated sections, one still pending; identifiers only, no names |
| `seed_ignite__school_nces_ids`     | `schoolid` to NCES school id; one id covers both Newark schools    |
| `int_ignite__student_id_crosswalk` | `student_number` to masked numeric `stu_id`; retained, never sent  |
| `int_ignite__attendance`           | `days_present` and `days_enrolled` per student per school per year |
| `int_ignite__state_assessment`     | NJSLA and NJGPA reshaped into the math and reading families        |
| `int_ignite__interim_assessment`   | iReady beginning-of-year and end-of-year by subject                |
| `int_ignite__treatment_assignment` | the seam; treated sections to students to the class-level flags    |
| `int_ignite__student_treatment`    | class-level flags rolled up to one row per student per year        |
| `rpt_ignite__student_level`        | Table 1                                                            |
| `rpt_ignite__course_level`         | Table 2                                                            |
| `rpt_ignite__teacher_course`       | anonymized classroom file returned to Mathematica                  |

No separate `int_ignite__enrollment_scaffold` was needed —
`rpt_ignite__student_level` derives the population and the longest-enrolled
school pick inline, which keeps the school-choice rule adjacent to the row it
governs.

NCES school identifiers are absent from the warehouse — every existing `nces_id`
column refers to a **college**, and every `nces_course_id` is a SCED course
code. Only three KIPP NJ schools enrol grades 9-12, so the seed holds three
rows. **The two Newark schools do share one NCES id** — confirmed against the
NCES school listing on 2026-09-30, which returns a single school for each KIPP
NJ district: `340007000529` for Newark and `340077703307` for Camden. KIPP's
campus structure is an internal delineation with no federal counterpart, so
there is no finer identifier to obtain. `school_id` therefore cannot distinguish
the two Newark treatment sites and Mathematica must key school-level analysis on
`school_name` instead; this also means a student who transferred between them
would collide on `(stu_id, school_id, school_year)`, which the longest-enrolled
rule avoids by emitting one row per student-year.

### Upstreams

All already exist:

- `int_extracts__student_enrollments` — demographics, program flags, enrollment
- `int_extracts__course_enrollments_by_term` — course grain plus teacher,
  course, section, period, semester
- `stg_powerschool__storedgrades` — course grades
- `int_powerschool__ps_adaadm_daily_ctod` — daily `attendancevalue` and
  `membershipvalue`
- `int_pearson__all_assessments` — NJSLA, NJGPA through SY2024-2025
- `int_cambium__all_assessments` — NJSLA, NJGPA from SY2025-2026
- `int_iready__diagnostic_results` — iReady diagnostics Course subject is
  derived from PowerSchool's `credit_type` with a four-branch `case`, not from
  `stg_google_sheets__crdc__sced_code_crosswalk`. The crosswalk is keyed on
  `nces_subject_area` plus `nces_course_id`, which this extract never needs, so
  joining it would add a dependency to reach four constants.

## Data flow

```text
int_extracts__student_enrollments ─┬─ int_ignite__enrollment_scaffold ─┐
                                   │                                   │
int_powerschool__ps_adaadm_daily_ctod ─ int_ignite__attendance ────────┤
                                                                       ├─ rpt_ignite__student_level
int_pearson__all_assessments ─┬─ int_ignite__state_assessment ────────┤
int_cambium__all_assessments ─┘                                        │
                                                                       │
int_iready__diagnostic_results ─ int_ignite__interim_assessment ───────┤
                                                                       │
int_ignite__student_id_crosswalk ──────────────────────────────────────┤
                                                                       │
google sheet (site-lead file) ── int_ignite__treatment_assignment ─────┤
                                                                       │
int_extracts__course_enrollments_by_term ─┬────────────────────────────┴─ rpt_ignite__course_level
stg_powerschool__storedgrades ────────────┘
                                          └──────────────────────────────  rpt_ignite__teacher_course
```

### ID masking and deidentification

`stu_id` derives from `student_number` by a salted `farm_fingerprint` reduced to
nine digits. Three properties drive this choice:

- Mathematica's template specifies `stu_id` as a **number with no decimals**, so
  `dbt_utils.generate_surrogate_key` is unusable — it returns a hex string.
- The mask must be reproducible between the phase-1 and phase-2 submissions or
  the two files will not join on Mathematica's end. A pure function guarantees
  this; a stored sequential assignment does not, because a `--full-refresh`
  would silently reassign every ID with no error.
- Reduction to nine digits introduces a small collision risk. A `unique` test on
  `stu_id` converts that risk into a build failure rather than silent
  corruption.

The agreement requires KIPP NJ to retain a crosswalk between masked and state
identifiers. Because the derivation is deterministic, that crosswalk is always
recomputable and cannot be lost.

Deidentification rules:

- `student_number` and `state_studentnumber` are never projected into any `rpt_`
  model. Only masked `stu_id` crosses that boundary.
- `int_ignite__student_id_crosswalk` is tagged `config.meta.contains_pii: true`
  and is never exported.
- `rpt_ignite__teacher_course` drops the teacher name column, per Mathematica's
  instruction to remove it and anonymize any other identifying field before
  upload.
- Both `rpt_` models set `contract: enforced: true`, per repo convention.

### The treatment seam (revised 2026-09-16)

The site-lead classroom list arrived on 2026-08-31 and again, expanded, on
2026-09-16. Resolving it disproved this spec's original assumption, so the
approach below replaces it.

**Course-name matching does not work.** The list numbers courses in Arabic
(`ENG100`, `Algebra 1`, `English 300`) where PowerSchool uses Roman
(`English I`, `Algebra I`, `English III`), and it appends an `ICR` label that is
not part of any PowerSchool course name. Teacher name is also unreliable as a
key, because five of the fifteen named teachers are in-class-resource
co-teachers who hold no section of record.

**What does work is class period plus the service-model suffix PowerSchool
carries in `section_number`** — `3ICR`, `56DBICR`, `2ICS`, `4consult` — with
teacher-of-record used as corroboration where the named teacher does hold the
section. On that basis 12 of 17 live classes resolved to an exact course and
section number; four further rows were withdrawn by the researchers themselves,
and five were sent back to school staff as numbered questions.

All five answers came back on 2026-09-30 and every class now maps to an exact
course and section number. Three resolved directly. One answer named two
sections rather than one, and both are treated. One named a course that does not
exist at that school, but both readings of it point at sections already in the
treatment set, so the ambiguity cannot change the population and the row is kept
only as an audit trail. The remaining answer ruled out the sole candidate its
question offered and identified a section taught under another teacher's name,
which school staff confirmed separately.

The resolved identifiers live in `seed_ignite__treatment_sections`, a seed of 18
rows carrying course and section numbers only. **Teacher names are deliberately
absent** — they are staff PII and must not enter a commit; the working
resolution sheet that holds them stays in `.claude/scratch/`. A row marked
`pending` would carry null identifiers and contribute no treated students;
filling such a row and rebuilding is the whole update path, and none is pending
now. A row marked `duplicate` names a section another row already resolves and
is excluded so the section join cannot fan out.

`int_ignite__treatment_assignment` expands that seed to the students enrolled in
each resolved section. Student-level flags roll up from the course grain: a
student receives `treatment_cp = 1` when they appear in any class where
`cls_treatment_cp = 1`, and likewise for `rdc` and `rr`.

**Only routine data cycles ran at KIPP NJ.** Mathematica confirmed on 2026-09-16
that `treatment_cp` and `treatment_rr` should be zero throughout, so the study
cannot estimate those two effects here. Verified treated populations are 67
students in school year 2025 and 151 in 2026.

### Population parameters

Region, grade level, and academic year are dbt vars, defaulting to the memo's
literal reading — all KIPP NJ grades 9-12 for academic years 2025 and 2026.
Narrowing to Newark only is a one-line change if Mathematica confirms the study
population excludes Camden.

### Academic year convention

Warehouse `academic_year_int` is the **start** year of a school year, so
`academic_year_int = 2025` corresponds to `academic_year = '2025-2026'`.
Mathematica defines `school_year` as the four-digit year at the **end** of the
school year. Every outbound `school_year` is therefore `academic_year_int` plus
one:

| Mathematica `school_year` | Warehouse `academic_year` | `academic_year_int` |
| ------------------------- | ------------------------- | ------------------- |
| 2025                      | 2024-2025                 | 2024                |
| 2026                      | 2025-2026                 | 2025                |

Getting this wrong shifts every row by a year with no error surfacing, so the
mapping is asserted by a test rather than left to convention.

### iReady interim coverage is partial

Verified 2026-08-06 against `kipptaf_iready.int_iready__diagnostic_results`,
distinct students in grades 9-12:

| Mathematica `school_year` | Grade 9 BOY / EOY | Grade 10 BOY / EOY | Grades 11-12 |
| ------------------------- | ----------------- | ------------------ | ------------ |
| 2025 (SY 2024-2025)       | 1 / 9             | 0 / 14             | negligible   |
| 2026 (SY 2025-2026)       | 541 / 495         | 464 / 338          | negligible   |

Two consequences:

- **`school_year` 2025 interim data is unusable.** Forty-six high school
  students in total, with beginning-of-year present for exactly one. iReady
  appears to have reached these grades only in 2025-2026.
- **Even in 2026, usable coverage is grades 9 and 10 only.** Grades 11 and 12
  carry roughly a dozen and under ten students respectively.

Interim columns are populated where data exists and left null elsewhere.
Mathematica should be told which cells are structurally empty rather than left
to infer it from blanks.

### The iReady partition duplication has cleared

When this was written, `int_iready__diagnostic_results` carried school year
2025-2026 under **both** `_dagster_partition_academic_year = 2025` and `= 2026`
with matching distinct student counts, so an unconstrained read double-counted
and `rn_subj_round = 1` did not resolve it.

Rechecked 2026-09-30: it no longer does. Each partition now maps to exactly one
academic year — 2024 to 2024-2025, 2025 to 2025-2026, 2026 to 2026-2027 — and
partition 2026 holds only BOY and Outside Round rows, which is what a school
year a month old looks like rather than a copy of a finished one. Across
partitions 2025 and 2026 only 117 of 19,079 records share a student, subject,
round and score, consistent with coincidence rather than duplication.

`int_ignite__interim_assessment` still filters `academic_year_int`, which is
still correct, but now because SY2026-2027 is genuinely out of scope rather than
because it is a duplicate. No issue needs filing.

### Column mapping — student level

| Mathematica field                                                          | Source                                            |
| -------------------------------------------------------------------------- | ------------------------------------------------- |
| `stu_id`                                                                   | `int_ignite__student_id_crosswalk`                |
| `school_year`                                                              | `academic_year_int` plus 1 — see year convention  |
| `school_id`                                                                | `seed_ignite__school_nces_ids`                    |
| `school_name`                                                              | `school_name`                                     |
| `treatment_cp`, `treatment_rdc`, `treatment_rr`                            | `int_ignite__treatment_assignment`, default `0`   |
| `grade_level`                                                              | `grade_level`                                     |
| `gender`                                                                   | `gender` or `aligned_gender`, with codebook       |
| `white`, `black`, `asian`, `amindian`, `multirace`, `missrace`, `hispanic` | exploded from `race_ethnicity` and `fedethnicity` |
| `frpl`                                                                     | `lunch_status`                                    |
| `ell`                                                                      | `lep_status` or `ml_status`                       |
| `iep`                                                                      | `iep_status` or `spedlep`                         |
| `days_present`, `days_enrolled`                                            | `int_ignite__attendance`                          |
| `test_score_m` and the math, reading, writing families                     | `int_ignite__state_assessment`                    |
| `iReady_boy_score_*`, `iReady_eoy_score_*`                                 | `int_ignite__interim_assessment`                  |

### Column mapping — course level

| Mathematica field                                  | Source                                           |
| -------------------------------------------------- | ------------------------------------------------ |
| `stu_id`                                           | `int_ignite__student_id_crosswalk`               |
| `school_year`, `school_id`                         | `academic_year_int` plus 1, NCES seed            |
| `course_number`, `section_number`, `course_period` | `int_extracts__course_enrollments_by_term`       |
| `subject`                                          | SCED crosswalk on `credit_type` or course number |
| `grade_level`, `semester`, `course_name`           | `int_extracts__course_enrollments_by_term`       |
| `treatment_*` and `cls_treatment_*`                | `int_ignite__treatment_assignment`, default `0`  |
| `course_selfcont`                                  | `is_self_contained`                              |
| `course_grade`                                     | `stg_powerschool__storedgrades`, letter form     |
| `passed`, `passed_c`                               | derived from `course_grade`                      |
| `classid`                                          | `sectionid`, supplied as the optional field      |

`semester` maps to `1` for fall and `2` for spring per the template codebook.
`course_grade` must be a letter in A, B, C, D, F, or W; numeric scales require a
letter mapping. Mathematica allows W, but `storecode = 'Y1'` never carries one
here — the population holds only A, B, C, D, F and nulls — so the
`accepted_values` test deliberately omits it, and a W appearing later should be
investigated rather than waved through.

## Sequencing around the blocker

The populated Teacher and Course Identification file has not been received from
either site lead. Mathematica's timeline placed that handoff in May or June
2026, and their 2026-06-10 reminder hedged on whether it had happened — "each
school and site lead will (or have) provide(d) a list."

Work splits cleanly:

**Buildable now, blocking nothing:** the ID crosswalk, enrollment scaffold,
attendance, state assessment, interim assessment, the NCES seed, and both `rpt_`
models with treatment flags defaulted to `0`.

**Buildable now against a stub:** `int_ignite__treatment_assignment` and
`rpt_ignite__teacher_course`. Populate the Google Sheet with a few hand-entered
rows drawn from real Newark sections, prove the join resolves to the correct
`course_number`, `section_number`, and period, then replace the contents when
the real file arrives. Nothing downstream changes.

This ordering means the arrival of the site-lead file flips flags rather than
starting work.

## Testing

- `unique` on `stu_id` in the crosswalk — the guard that makes fingerprint
  collision a loud failure
- `dbt_utils.unique_combination_of_columns` on `stu_id` and `school_year` for
  Table 1
- `dbt_utils.unique_combination_of_columns` on `stu_id`, `school_year`,
  `course_number`, `section_number`, and `semester` for Table 2
- `dbt_utils.expression_is_true` asserting `days_present` is at most
  `days_enrolled`
- `accepted_values` on `course_grade` limited to the letters the population
  actually produces, A, B, C, D and F
- `relationships` from `rpt_ignite__course_level.stu_id` to the crosswalk
- unmatched site-lead rows test on the seam
- `not_null` on every field Mathematica marks required

## Delivery

Outbound files are assembled into Mathematica's
`NJCF_Marshall Administrative_Data Template.xlsx` and uploaded to their Box site
by the data liaison. The agreement and every Mathematica message prohibit
transferring data by email or public transfer service.

Box access may not yet be provisioned — Mathematica offered on 2026-07-29 to
"provide the link for where you can update the data," which suggests it is not.
Confirm access before a file is ready rather than after.

## Open questions

1. **What does Mathematica expect for 2024-2025 interim data, given it was not
   collected?** Resolved by query that iReady reached grades 9-10 only in
   2025-2026 (see coverage above); school year 2025 has 46 high school students
   and one beginning-of-year record. The columns cannot be populated. Confirm
   whether Mathematica wants them left null, wants grades 11-12 excluded from
   the interim analysis, or expects a different instrument for high school — the
   memo also offers MAP, aimsWeb, and FastBridge column families.
2. **Does the population include Camden?** The agreement names "KIPP NJ" and the
   memo says "all students within the CMO," but both treatment schools are
   Newark and all coordination has been Newark-titled. Parameterized either way;
   needs Mathematica's confirmation.
3. **How should mid-year transfers pick a school?** The memo specifies the
   school from the site-lead list, otherwise the school where the student was
   enrolled longest. Confirm against how `int_extracts__student_enrollments`
   picks a row.
4. **Are accommodation and exemption codes available** for NJSLA and NJGPA at
   the grain Mathematica wants, including students with multiple accommodations?
   Partly resolved. Pearson supplied yes/no flags and no codes, and populated
   them sparsely. Cambium, which replaced Pearson for SY2025-2026, **does**
   supply them — `unique_accommodation`, `ml_accommodation` and
   `iep_exempt_from_passing` are all present in the District Summative Record
   File — but `stg_cambium__njsla` projects 28 of that file's 228 columns and
   does not include them, so they are unreachable downstream today. Every
   SY2025-2026 row is therefore null on all four accommodation and exemption
   columns. That understates the truth for **486 of the 901** IGNITE students
   who sat the SY2025-2026 NJSLA, each carrying at least one accommodation and
   some as many as seven — `text_to_speech` on 286, `frequent_breaks` and
   `small_group_testing` on 101 each, `extended_time` on 99. The file also
   carries roughly thirty individually named accommodation columns, which is
   exactly the "multiple variables" Mathematica anticipates for `accom_code_*`,
   so that family is fillable too rather than absent for want of a code. Wiring
   them through is a cross-project change: the columns must be added to the
   cambium package and `int_cambium__all_assessments`, and reach kipptaf only
   after a district prod rebuild. It also needs a mapping rather than a
   passthrough, because Cambium redefined the exemption field from Pearson's
   `Y`/`N` flag to `N` plus the codes `B`, `E` and `M`, so a `= 'Y'` test would
   never fire. Separately, confirm whether Mathematica would rather have a blank
   than a zero where no answer exists at all.
