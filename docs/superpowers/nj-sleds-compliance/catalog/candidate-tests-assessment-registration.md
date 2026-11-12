# Candidate dbt tests from the NJ State Assessment Registration (SAR)

Draft for a data team planning session, 2026-10-20. Proposals only; nothing here
is built or run. No student data.

Inputs: `assessment-registration-fields.md` (the "SAR catalog"; check IDs
S1-S24, M1-M14, citation keys PS-SAR, SM-HB, PS-RN-x),
`existing-tests-inventory.md`, `powerschool-ingestion-gaps.md`, issue #5558
("What backs up a ticketed test"), `rpt_tableau__state_testing_accomodations`,
`rpt_gsheets__nj_state_test_roster`, `dim_student_iep_status`,
`dim_student_ell_status`, and the `stg_powerschool__s_nj_stu_x` contract.

## How to read this

### Constraints every row inherits

- **Routing host.** #5558 puts a ticketed test at `severity: warn` on the
  earliest model that carries record ID, school, region, and period. The package
  `stg_powerschool__s_nj_stu_x` carries only `studentsdcid`, so no SAR check can
  be ticketed there.
- **Backup code.** Each ticketed row also needs a runbook, a defending model,
  and an error-level regression test (Section C). Not repeated per row.
- **Current state only.** `s_nj_stu_x` holds one row per student and no history.
  Tickets can cover only today's values, not "every record the test has ever
  covered" (#5558).
- **Views go dormant.** A test on a view runs only when the view's SQL changes.
  RPT-TAB and RPT-GS are views (no table config under kipptaf `extracts/`), so
  neither can host a ticketed test.
- **PII.** Every stored failure row is student-level PII.

### Hosts

- `H-REG`: proposed; does not exist (P1). A kipptaf domain `int_`,
  `materialized: table`, NJ regions including Paterson. It joins
  `stg_powerschool__s_nj_stu_x` to `int_extracts__student_enrollments`
  (`rn_year = 1`) on `studentsdcid = students_dcid` and `_dbt_source_project`.
  It carries `student_number`, `_dbt_source_project`, `region`, `schoolid`,
  `academic_year`, `grade_level`, `school_level`, `enroll_status`, the status
  booleans below, and the registration columns each row needs. Shape is open
  (D-7).
- `ENR`: `int_extracts__student_enrollments` (exists, table).
- `RPT-TAB`: `rpt_tableau__state_testing_accomodations` (view). Feeds the State
  Testing Accommodations Tracker. Newark and Camden only, current year,
  `enroll_status = 0`.
- `RPT-GS`: `rpt_gsheets__nj_state_test_roster` (view). Feeds the NJ State Test
  Roster sheet. Grades 3-9 and 11, not Miami, so Paterson is included.

### Predicate shorthand

- `on(x)`: flag column `x` is set. The stored "set" value is unconfirmed (P3).
  `asmt_*` and `parcc_*` are STRING (the SAR outputs `Y`); `sla_*` and `*_tf`
  are INT64.
- `is_iep`, `is_504`, `is_ml`: status booleans; source to be chosen (P2, D-3).
  Today's in-house values: `ENR.spedlep like 'SPED%'`, `ENR.is_504`,
  `ENR.lep_status`.
- `tested_grade`: `grade_level in (3, 4, 5, 6, 7, 8, 9, 11)`, from RPT-GS's
  filter. No PowerSchool or NJ source in the catalog states it.
- `SWD_COLS` (SAR #53-79 sources): `asmt_frequent_breaks`,
  `asmt_alternate_location`, `asmt_small_group`, `asmt_special_equip`,
  `asmt_specified_area`, `asmt_time_of_day`, `asmt_answer_masking`,
  `asmt_read_aloud`, `asmt_color_contrast`, `asmt_asl_video`,
  `asmt_screen_reader`, `asmt_non_screen_reader`, `asmt_closed_caption_ela`,
  `asmt_refresh_braille_ela`, `asmt_alt_rep_paper`, `parcc_large_print_paper`,
  `asmt_braille_tactile_paper`, `asmt_human_signer`,
  `asmt_answers_recorded_paper`, `asmt_braille_response`, `parcc_math_tools`,
  `parcc_constructed_response_ela`, `asmt_selected_response_ela`,
  `asmt_math_response`, `asmt_monitor_response`, `asmt_word_prediction`. #70 has
  no source field.
- `ML_COLS` (#39, #81-83): `parcc_ell_paper_accom`, `asmt_directions_aloud`,
  `asmt_math_response_el`, `parcc_translation_math_paper`.
- `MATH_ONLY`: `parcc_math_tools` / `calculation_device_math_tools`,
  `asmt_math_response`, `parcc_translation_math_paper`, `asmt_text_to_speech`
  02-05. `ELA_ONLY`: `asmt_closed_caption_ela`, `asmt_refresh_braille_ela`,
  `parcc_constructed_response_ela`, `asmt_selected_response_ela`,
  `asmt_text_to_speech` 01.
- `DLM_MATH`: the `math_state_assessment_name` codes that mean DLM for math. The
  in-house models disagree (`'3'` vs `'3', '4'`; D-4).
- Coded domains for SAR-31 (S22): `asmt_color_contrast` 01-07 (plus 1 value
  added in PS-RN-26.6.2.0); `asmt_braille_response` 01-02; `parcc_math_tools`
  C/T/B; `parcc_constructed_response_ela`, `asmt_selected_response_ela`,
  `asmt_math_response` 01-04; `asmt_directions_aloud` ARA, CHI, HAT, NAV, POL,
  POR, RUS, SPA, UD, VIE, HT, BEN, KOR; `asmt_math_response_el` 01-02;
  `parcc_translation_math_paper` SPA; `asmt_text_to_speech` 01-05;
  `asmt_emergency_accommodation` 01, 99; `asmt_extended_time` and
  `asmt_extended_time_math` Both, IEP504, ML, EL.

### Other codes

- Test form: `eit` = model-level `dbt_utils.expression_is_true` scoped with
  `config.where` (all predicates are row-local); `av` = column `accepted_values`
  (passes NULL); `sing` = singular test; `ucc` =
  `dbt_utils.unique_combination_of_columns`. Ticketed forms run at warn.
- Fix owner: `TC` school testing coordinator; `SPED`; `ELL`; `DT` data team.
- Prereqs:
  - P1: build `H-REG`.
  - P2: choose the status sources (D-3).
  - P3: confirm the stored flag values.
  - P4: find which accommodation column set is live (D-2).
  - P5: get a valid NJ test-code list. The PS Test Codes appendix was not
    captured; the successor template spec would also do.
  - P6: confirm the in-house `state_assessment_name` codes (D-4).
  - P7: confirm what the exclude flags mean (D-5).
  - P8: get a staff SMID source. `s_nj_usr_x` and `s_nj_ssf_x` are not ingested
    in any region.
  - P9: get the ML first-year cutoff date (ELL office).
- Overlap: "RPT-TAB all" means RPT-TAB reads every column the predicate needs,
  so the rule could be checked by eye on the dashboard. "RPT-TAB some" means it
  reads part of them. RPT-TAB implements none of these rules; it only unpivots
  and displays values.
- Still relevant: the last column names successors by release-note title only.
  Template specs were not captured, so every "feeds" is an inference.
  - `SAF`: NJSLA/NJGPA-Adaptive Student Attributes accommodation mapping
    (PS-RN-26.6.2.0).
  - `ASF`: NJSLA/NJGPA-Adaptive Student File (PS-RN-26.3.2.0).
  - `TIDE`: NJSLEDS TIDE Student File (PS-RN-26.10.1.0).
  - `DASH`: RPT-TAB's dashboard. `ROSTER`: RPT-GS's sheet.

## Section A: Candidate tests

40 candidates: 11 H, 17 M, 12 L. 35 are SAR-only. 27 touch RPT-TAB columns (11
fully, 16 partly).

### A1. Accommodations that require a status

| id     | rule                                                                                         | predicate                                                                                                                                                                                             | source citation                | SAR-only or also SM | host model | test form | fix owner                   | source-fixable? | prereqs    | overlap                                 | confidence | still relevant after deprecation?                         |
| ------ | -------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ | ------------------- | ---------- | --------- | --------------------------- | --------------- | ---------- | --------------------------------------- | ---------- | --------------------------------------------------------- |
| SAR-01 | Unique Accommodation only with an IEP, 504, or EL plan                                       | `on(asmt_unique_accommodation) and not (is_iep or is_504 or is_ml)`                                                                                                                                   | PS-SAR Report Output r87 (S14) | SAR-only            | H-REG      | eit       | SPED                        | Y               | P1-P3      | RPT-TAB all                             | H          | Y: SAF, DASH                                              |
| SAR-02 | Extended Time code matches status: IEP504 needs IEP/504; ML or EL needs ML; Both needs both  | for `x` in (`asmt_extended_time`, `asmt_extended_time_math`): `(x = 'IEP504' and not (is_iep or is_504)) or (x in ('ML', 'EL') and not is_ml) or (x = 'Both' and not (is_ml and (is_iep or is_504)))` | r89 (S15)                      | SAR-only            | H-REG      | eit       | SPED (IEP504); ELL (ML, EL) | Y               | P1, P2     | RPT-TAB all; RPT-GS reads presence only | H          | Y: ROSTER extended-time columns, SAF, DASH                |
| SAR-03 | Directions Clarified in Native Language only for an English learner                          | `on(asmt_directions_clarified) and not is_ml`                                                                                                                                                         | r80 (S16)                      | SAR-only            | H-REG      | eit       | ELL                         | Y               | P1-P3      | RPT-TAB all                             | H          | Y: SAF, DASH                                              |
| SAR-04 | Other ML-labeled accommodations only for an English learner                                  | `(on(parcc_ell_paper_accom) or asmt_directions_aloud is not null or asmt_math_response_el is not null or parcc_translation_math_paper is not null) and not is_ml`                                     | r39 (S17); r81-83 by label     | SAR-only            | H-REG      | eit       | ELL                         | Y               | P1-P3      | RPT-TAB all                             | M          | Y: SAF, DASH                                              |
| SAR-05 | Disability accommodations only with an IEP, 504, or EL plan (Emergency Accommodation exempt) | `<any SWD_COLS set> and not (is_iep or is_504 or is_ml)`                                                                                                                                              | r53-79; r87 wording; r88       | SAR-only            | H-REG      | eit       | SPED                        | Y               | P1-P4      | RPT-TAB some                            | L          | Y: SAF, DASH, if SPED confirms the rule (D-10)            |
| SAR-06 | Exempt From Passing only for a high school student with an IEP                               | `on(parcc_exempt_from_passing) and not (grade_level between 9 and 12 and is_iep)`                                                                                                                     | r33 (S6)                       | SAR-only            | H-REG      | eit       | SPED                        | Y               | P1-P3      | none                                    | H          | Y: graduation status; may pair with SM pathway `M` (D-12) |
| SAR-07 | ML Exempt From Taking ELA only for an English learner in a first US-school year              | `pid_lepexemptlal_tf = 1 and (not is_ml or asmt_first_enroll_in_us_school is null or asmt_first_enroll_in_us_school < <cutoff>)`                                                                      | r31, r38 (S7)                  | SAR-only            | H-REG      | eit       | ELL                         | Y               | P1, P2, P9 | none                                    | M          | Y: ELA exemption (ROSTER, ASF)                            |

### A2. Status sources agree

| id     | rule                                                                 | predicate                                                                                                                                       | source citation                             | SAR-only or also SM                   | host model | test form | fix owner | source-fixable? | prereqs                           | overlap                                            | confidence | still relevant after deprecation?                                    |
| ------ | -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- | ------------------------------------- | ---------- | --------- | --------- | --------------- | --------------------------------- | -------------------------------------------------- | ---------- | -------------------------------------------------------------------- |
| SAR-08 | NJSLA-page 504 flag matches the in-house 504 status                  | `(pid_504_tf = 1) != coalesce(ENR.is_504, false)`                                                                                               | r29 (S10); SAR catalog Q4                   | SAR-only (no SM element)              | H-REG      | eit       | SPED      | Y               | P1                                | RPT-TAB some (`c_504_status` is the in-house side) | M          | Y: DASH and ROSTER 504 columns; the SAR was the only state 504 field |
| SAR-09 | PowerSchool disability code matches the EdPlan IEP status            | `(specialed_classification is not null) != (spedlep like 'SPED%')`; adjust if a "no disability" code is stored                                  | r30; SM-HB p.91-93 (M6)                     | Also SM                               | H-REG      | eit       | SPED      | Y               | P1                                | RPT-TAB some (EdPlan side)                         | M          | Y: DASH IEP columns; SM SpecialEducationClassification               |
| SAR-10 | NJSLA ML status matches the in-house ML status (LEP dates)           | `(state_ell_status in (<current-ML codes>)) != lep_status`                                                                                      | r24, r34; SM-HB p.95 (M12)                  | Also SM (different PS field)          | H-REG      | eit       | ELL       | Y               | P1; `state_ell_status` domain n/s | RPT-TAB some (`lep_status`)                        | M          | Y: DASH and `dim_student_ell_status` use LEP dates                   |
| SAR-11 | ML status R if and only if a current ML's parent refused services    | `(state_ell_status = 'R' and liep_parent_refusal_date is null) or (liep_parent_refusal_date is not null and is_ml and state_ell_status != 'R')` | r34 (S8); SM-HB p.105                       | SAR-only (R code); refusal date is SM | H-REG      | eit       | ELL       | Y               | P1, P2                            | none                                               | M          | Y?: only if TIDE carries ML status                                   |
| SAR-12 | In-house "ACCESS only, ML exempt" code matches the PS ML-exempt flag | `(state_assessment_name = '2') != (pid_lepexemptlal_tf = 1)`                                                                                    | r31, r37; code meaning is in-house (RPT-GS) | SAR-only                              | H-REG      | eit       | ELL       | Y               | P1, P6                            | RPT-GS logic; RPT-TAB some                         | M          | Y: ROSTER ELA exemption                                              |
| SAR-13 | Title III status only for an English learner                         | `on(pid_title3status) and not is_ml`                                                                                                            | r25 (S11)                                   | SAR-only                              | H-REG      | eit       | ELL       | Y               | P1-P3                             | none                                               | M          | N, unless TIDE carries it: no dbt consumer                           |

### A3. A status that should prompt a review

| id     | rule                                                                              | predicate                                                                                                                                            | source citation                                    | SAR-only or also SM | host model | test form        | fix owner | source-fixable?             | prereqs | overlap      | confidence | still relevant after deprecation? |
| ------ | --------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- | ------------------- | ---------- | ---------------- | --------- | --------------------------- | ------- | ------------ | ---------- | --------------------------------- |
| SAR-14 | Student with an IEP or 504 in a tested grade has no testing accommodation         | `(is_iep or is_504) and tested_grade and <no SWD_COLS set> and asmt_extended_time is null and asmt_extended_time_math is null`                       | Implied by r87 (accommodations come from the plan) | SAR-only            | H-REG      | eit, review list | SPED      | Y if missing; often correct | P1-P4   | RPT-TAB some | L          | Y: DASH review list               |
| SAR-15 | English learner in a tested grade has no ML accommodation and no ML extended time | `is_ml and tested_grade and coalesce(asmt_extended_time, '') not in ('ML', 'EL', 'Both') and not on(asmt_directions_clarified) and <no ML_COLS set>` | Implied by r80-83, r89                             | SAR-only            | H-REG      | eit, review list | ELL       | Y if missing; often correct | P1-P3   | RPT-TAB all  | L          | Y: DASH review list               |

### A4. Test assignment and grade eligibility

| id     | rule                                                                               | predicate                                                                                                                                                                                                                                         | source citation                                                 | SAR-only or also SM | host model | test form | fix owner      | source-fixable? | prereqs                                          | overlap                                                                                                 | confidence | still relevant after deprecation?                                                      |
| ------ | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- | ------------------- | ---------- | --------- | -------------- | --------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------- |
| SAR-16 | DLM (alternate assessment) only for a student with an IEP                          | `(state_assessment_name in ('3', '4') or math_state_assessment_name in DLM_MATH) and not is_iep`                                                                                                                                                  | r37 (no domain in PS-SAR); code meanings in-house (RPT-GS)      | SAR-only            | H-REG      | eit       | SPED           | Y               | P1, P2, P6                                       | RPT-TAB all; RPT-GS, `is_exempt_state_testing`, `int_reporting__promotional_status` read the same codes | M          | Y: ASF drops DLM students (PS-RN-26.3.2.0), so a wrong code drops a student from NJSLA |
| SAR-17 | ACCESS-coded assessment name only for an English learner                           | `state_assessment_name in ('2', '4') and not is_ml`                                                                                                                                                                                               | r37; code meanings in-house                                     | SAR-only            | H-REG      | eit       | ELL            | Y               | P1, P2, P6                                       | RPT-TAB all; RPT-GS                                                                                     | M          | Y: ROSTER exemption reason                                                             |
| SAR-18 | State Assessment Name holds only known codes                                       | `av` on `state_assessment_name` and `math_state_assessment_name`; values TBD (in-house uses 2, 3, 4)                                                                                                                                              | r37 (Numeric 1, domain n/s)                                     | SAR-only            | H-REG      | av        | TC             | Y               | P1, P6                                           | RPT-TAB all                                                                                             | L          | Y: ROSTER and ASF depend on the codes                                                  |
| SAR-19 | A test-code override matches the grade                                             | ELA: `parcc_ela_test_code != if(grade_level = 11, 'ELAGP', concat('ELA0', grade_level))`. Math: `parcc_math_test_code` not in the grade's set (`MAT0` + grade for 3-8; ALG01, GEO01, ALG02 for MS/HS; MATGP for 11). Skip when `on(parcc_retest)` | r49 and Selection Criteria (S4); code names from RPT-GS         | SAR-only            | H-REG      | eit       | TC             | Y               | P1, P5                                           | RPT-GS derives its own codes and ignores overrides                                                      | M          | Y: TIDE registration (inference)                                                       |
| SAR-20 | ELA and Math code fields each hold their own subject                               | `parcc_ela_test_code not like 'ELA%' or left(parcc_math_test_code, 3) not in ('MAT', 'ALG', 'GEO')`                                                                                                                                               | r49 (S4)                                                        | SAR-only            | H-REG      | eit       | TC             | Y               | P1, P5                                           | none                                                                                                    | M          | Y: TIDE (inference)                                                                    |
| SAR-21 | No test-code override in an untested grade unless it is a retest                   | `coalesce(parcc_ela_test_code, parcc_math_test_code, sla_test_code) is not null and (grade_level < 3 or (grade_level in (10, 12) and not on(parcc_retest)))`                                                                                      | r49, r51; grade span from RPT-GS                                | SAR-only            | H-REG      | eit       | TC             | Y               | P1, P3, P5                                       | none                                                                                                    | L          | Y: TIDE (inference)                                                                    |
| SAR-22 | A grade 9 high school student has an Algebra I, Geometry, or Algebra II section    | `school_level = 'HS' and grade_level = 9 and math_course is null`. `math_course` comes from `base_powerschool__course_enrollments` NCES 052/072/056, as in RPT-GS                                                                                 | Selection Criteria (S1); RPT-GS emits `NO MATH COURSE ASSIGNED` | SAR-only            | H-REG      | eit       | TC (scheduler) | Y               | P1                                               | RPT-GS logic                                                                                            | H          | Y: ROSTER math test code                                                               |
| SAR-23 | A tested-grade student has an active ELA and math section, or a test-code override | `tested_grade and enroll_status = 0 and ((not has_ela_section and parcc_ela_test_code is null) or (not has_math_section and parcc_math_test_code is null))`                                                                                       | Selection Criteria (S1)                                         | SAR-only            | H-REG      | eit       | TC (scheduler) | Y               | P1; "valid class" is undefined (SAR catalog Q12) | Existing `int_students__course_enrollments__core_sections_cover_k8` (region-level 95%, K-8 only)        | M          | Y?: whether TIDE selects by class was not captured                                     |

### A5. Exclusion flags

| id     | rule                                                                      | predicate                                                                                                                                                                                                                                                                                       | source citation                               | SAR-only or also SM | host model | test form                  | fix owner   | source-fixable? | prereqs    | overlap                                                               | confidence | still relevant after deprecation?                 |
| ------ | ------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- | ------------------- | ---------- | -------------------------- | ----------- | --------------- | ---------- | --------------------------------------------------------------------- | ---------- | ------------------------------------------------- |
| SAR-24 | An exclude flag has a recorded reason, and a recorded reason has the flag | A: `asmt_exclude_ela = 1 and not (state_assessment_name in ('2', '3', '4') or graduation_pathway_ela = 'M' or pid_lepexemptlal_tf = 1)`; math uses `math_state_assessment_name in DLM_MATH` and `graduation_pathway_math = 'M'`. B: a reason is present and `coalesce(asmt_exclude_ela, 0) = 0` | r45, r49 list these fields; their role is n/s | SAR-only            | H-REG      | eit (A ticketed; B review) | TC          | Y               | P1, P6, P7 | RPT-TAB some (passes `asmt_exclude_*`); RPT-GS ignores them           | L          | Y?: if successor files read them; DASH shows them |
| SAR-25 | NJSLA-page exclude flag agrees with the per-subject flags                 | `sla_exclude_tf` vs `asmt_exclude_ela` / `asmt_exclude_math` disagree (mapping TBD)                                                                                                                                                                                                             | Not in PS-SAR; staging contract only          | Not in SAR spec     | H-REG      | eit                        | DT, then TC | Y after P7      | P1, P4, P7 | RPT-TAB some (`asmt_exclude_*` only); no model reads `sla_exclude_tf` | L          | Y?: same as SAR-24                                |

### A6. Test format

| id     | rule                                                                      | predicate                                                                                                                                                          | source citation                       | SAR-only or also SM | host model | test form | fix owner | source-fixable? | prereqs                       | overlap      | confidence | still relevant after deprecation?                                      |
| ------ | ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------- | ------------------- | ---------- | --------- | --------- | --------------- | ----------------------------- | ------------ | ---------- | ---------------------------------------------------------------------- |
| SAR-26 | Test Format is P or O                                                     | `parcc_test_format in ('P', 'O')`; blank allowed (report default). Add `sla_test_format`, `access_test_format_override` once their domains are known               | r50 (S5)                              | SAR-only            | H-REG      | av        | TC        | Y               | P1                            | RPT-TAB all  | H          | Y: TIDE (inference), DASH                                              |
| SAR-27 | Translation of Math only on a paper test                                  | `parcc_translation_math_paper is not null and parcc_test_format = 'O'`                                                                                             | r83 (S18)                             | SAR-only            | H-REG      | eit       | ELL       | Y               | P1                            | RPT-TAB all  | H          | Y: SAF, DASH                                                           |
| SAR-28 | Paper-only accommodations not on an online test                           | `(on(asmt_alt_rep_paper) or on(parcc_large_print_paper) or asmt_braille_tactile_paper is not null or on(asmt_answers_recorded_paper)) and parcc_test_format = 'O'` | r67 stated; r68-69, r72 implied (S19) | SAR-only            | H-REG      | eit       | SPED      | Y               | P1, P3                        | RPT-TAB some | M          | Y: SAF, DASH                                                           |
| SAR-29 | Online-only accommodations not on a paper test                            | `(on(asmt_screen_reader) or on(asmt_non_screen_reader) or <TTS column> is not null) and parcc_test_format = 'P'`                                                   | r63-64, r85 (S20)                     | SAR-only            | H-REG      | eit       | SPED      | Y               | P1, P3, P4 (which TTS column) | RPT-TAB some | M          | Y: SAF, DASH                                                           |
| SAR-30 | ACCESS-only fields hold valid values and appear only for English learners | `access_tier_paper_tests not in ('A', 'B', 'C', '-')`; `(access_tier_paper_tests is not null or on(alternate_access)) and not is_ml`                               | r40-41 (S9)                           | SAR-only            | H-REG      | av + eit  | ELL       | Y               | P1-P3                         | RPT-TAB some | M          | N?: Pre-ID for ACCESS is Legacy; the ACCESS path is not in the catalog |

### A7. Code domains and subject scope

| id     | rule                                                                           | predicate                                                                                                                           | source citation                       | SAR-only or also SM | host model | test form        | fix owner | source-fixable? | prereqs                                                | overlap      | confidence | still relevant after deprecation?                                |
| ------ | ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- | ------------------- | ---------- | ---------------- | --------- | --------------- | ------------------------------------------------------ | ------------ | ---------- | ---------------------------------------------------------------- |
| SAR-31 | Coded accommodation fields hold only listed values                             | `av` per column (domains in the legend)                                                                                             | r61, 73-77, 81-83, 85-86, 88-89 (S22) | SAR-only            | H-REG      | av               | TC        | Y               | P1, P4; Color Contrast gained a value (PS-RN-26.6.2.0) | RPT-TAB some | H          | Y: SAF; values were relabeled in 26.6.2.0, so re-derive domains  |
| SAR-32 | Subject-only accommodation on a student who does not take that subject's NJSLA | `math_state_assessment_name in DLM_MATH and <any MATH_ONLY set>`; `state_assessment_name in ('2', '3', '4') and <any ELA_ONLY set>` | r65-66, 74-77, 83, 85 (S21)           | SAR-only            | H-REG      | eit, review list | SPED      | Y               | P1, P4, P6                                             | RPT-TAB some | L          | N?: SAF now marks other-subject accommodations off (PSSR-433240) |

### A8. Conflicts between accommodation column sets

| id     | rule                                                                    | predicate                                                                                                                                                                                                                       | source citation                                                                                                                    | SAR-only or also SM | host model | test form | fix owner                   | source-fixable? | prereqs    | overlap                                     | confidence | still relevant after deprecation?                     |
| ------ | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | ------------------- | ---------- | --------- | --------------------------- | --------------- | ---------- | ------------------------------------------- | ---------- | ----------------------------------------------------- |
| SAR-33 | Spec and non-spec copies of Calculation Device and Text-to-Speech agree | `parcc_math_tools != calculation_device_math_tools`; `asmt_text_to_speech != coalesce(parcc_text_to_speech, parcc_text_to_speech_math)`; both sides set                                                                         | r74, r85; SAR catalog section 5, Q3                                                                                                | SAR-only            | H-REG      | eit       | DT (pick live set), then TC | Y after P4      | P1, P4     | RPT-TAB some (reads the non-spec side only) | M          | Y: DASH shows blanks if the spec copy is the live one |
| SAR-34 | Human Reader or Signer code agrees with its source flags                | `(asmt_humanreader_signer = '01') != on(asmt_human_signer)`; `(asmt_humanreader_signer = '02') != (on(asmt_ih) or on(asmt_lh) or on(asmt_ri) or on(asmt_rl))`                                                                   | r86 (how the 5 sources combine is n/s)                                                                                             | SAR-only            | H-REG      | eit       | DT, then SPED               | Y after P4      | P1, P3, P4 | RPT-TAB some                                | L          | Y: DASH                                               |
| SAR-35 | Each `asmt_*` / `parcc_*` field agrees with its `sla_*` twin            | Per pair, e.g. `on(asmt_frequent_breaks) != (sla_frequent_breaks = 1)`; codes `asmt_extended_time` vs `sla_extended_time`, `asmt_text_to_speech` vs `sla_text_to_speech`, `asmt_humanreader_signer` vs `sla_humanreader_signer` | Not in PS-SAR or the SAR catalog; the `sla_*` set is in the staging contract only. Link to the PS-RN-26.6.2.0 relabel is inference | Not in SAR spec     | H-REG      | eit       | DT, then TC                 | Y after P4      | P1, P3, P4 | RPT-TAB some (`asmt_*` side)                | L          | Y: DASH; `sla_*` may be the successor fields          |

### A9. Scope and selection

| id     | rule                                                                              | predicate                                                                                                                                                                                                         | source citation                       | SAR-only or also SM                                   | host model                           | test form          | fix owner      | source-fixable? | prereqs                               | overlap        | confidence | still relevant after deprecation?                                                    |
| ------ | --------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- | ----------------------------------------------------- | ------------------------------------ | ------------------ | -------------- | --------------- | ------------------------------------- | -------------- | ---------- | ------------------------------------------------------------------------------------ |
| SAR-36 | Paterson students appear in the accommodations dashboard                          | RPT-TAB filters `region in ('Newark', 'Camden')`. Fails when Paterson has current enrolled students in ENR but 0 rows in RPT-TAB                                                                                  | SAR catalog section 5, Q17 (in-house) | n/a (in-house)                                        | RPT-TAB                              | Code fix plus R-08 | DT             | N               | D-6 decision                          | RPT-TAB itself | H          | Y: DASH                                                                              |
| SAR-37 | An enrolled tested-grade student is in NJ SMART extracts at a school that reports | `enroll_status = 0 and tested_grade and coalesce(includeinnjsmart_tf, 0) != 1`; school `state_excludefromreporting = 0`                                                                                           | Selection Criteria (S3); PS-SID       | SAR-only per catalog; the same flag gates SM extracts | H-REG                                | eit                | TC (registrar) | Y               | P1                                    | none           | H          | Y: the flag also gates SM extracts and Pre-ID for ACCESS                             |
| SAR-38 | No enrollment exits before it enters                                              | `entrydate < exitdate`                                                                                                                                                                                            | Selection Criteria (S2)               | SAR-only (SM-HB lacks it)                             | `int_powerschool__ps_enrollment_all` | eit (exists, warn) | TC (registrar) | Y               | none                                  | Existing test  | H          | Y: already covered; no new test                                                      |
| SAR-39 | Accountable county, district, and school codes are well formed when set           | `access_accountableschool` is 3 digits; `access_accountablecounty` and `access_accountabledistrict` are CDS-shaped (or the `sla_accountable_site_*` set, P4). Blank falls back to resident codes, so blank passes | r4-5 (S23); SM-RR p.1                 | SAR-only                                              | H-REG                                | eit                | TC             | Y               | P1; r5 spec defects (SAR catalog Q11) | none           | L          | Y?: SM-RR still assigns the accountable school "in the SAR"; successor field unknown |
| SAR-40 | Examiner and staff SMIDs are numeric and the stated length                        | `not regexp_contains(parcc_examiner_smid_ela, r'^\d{8}$')` (and `_math`); `parcc_staff_smid_override_ela` / `_math` match `^\d{10}$`                                                                              | r47-48 (S24)                          | SAR-only                                              | H-REG                                | eit                | TC             | Y               | P1, P8 (no SMID roster to join)       | none           | L          | N?: session staff likely moves to a successor; not captured                          |

### Checks not carried

- S12 Former IEP: the catalog gives no rule beyond "default null", and nothing
  reads it.
- S13 Special Education Placement: PowerSchool made the field obsolete in
  26.8.2.0 and removed it from the template in 26.9.1.0. Drop it.
- S4 as a full list check: it needs the Test Codes appendix (P5). SAR-19 and
  SAR-20 are partial substitutes.
- M1-M14: these are Student Management checks and belong in that catalog.
  `int_students__student_enrollments` already tests the M5 homeless code
  domains.

## Section B: What replaces the SAR

Facts from the SAR catalog only. The replacement is an inference from timing and
titles; no source says "this replaces the SAR".

| Successor                               | Catalog fact                                                                                                    | Source                      | Candidates that would transfer (inference)                                                                                                                                                        |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------------- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NJSLEDS TIDE Student File               | Template "updated to meet the format requirements for student registration in the 2026–27 assessment year"      | PS-RN-26.10.1.0 PSSR-453540 | Test assignment and selection: SAR-16 to SAR-23, SAR-26, SAR-37; maybe SAR-39                                                                                                                     |
| NJSLA/NJGPA-Adaptive Student File       | Now excludes students assigned to DLM for Math and ELA                                                          | PS-RN-26.3.2.0 PSSR-426313  | DLM gating: SAR-16, SAR-18, SAR-24. A wrong DLM code now silently removes a student from the NJSLA file, so SAR-16 matters more                                                                   |
| NJSLA/NJGPA-Adaptive Student Attributes | Accommodation mapping, "ensuring accommodations for one subject are marked off for the other"                   | PS-RN-26.6.2.0 PSSR-433240  | All accommodation rows: SAR-01 to SAR-05, SAR-14, SAR-15, SAR-27 to SAR-31, SAR-33 to SAR-35. SAR-32 may be redundant                                                                             |
| NJSLA accommodation fields relabeled    | Labels and values updated; Color Contrast gained a value; Braille Display data kept in a new Presentation field | PS-RN-26.6.2.0 PSSR-433366  | Re-derive the SAR-31 domains. Column-set rows SAR-33 to SAR-35. The staging contract has `presentation`, `embedded_co_writer_ela`, and the `sla_*` set; linking them to this release is inference |
| Pre-ID for ACCESS                       | Filed under Legacy                                                                                              | PS-TREE                     | SAR-30 has no known successor in the catalog                                                                                                                                                      |

What the catalog does not establish:

- Whether these templates replace the SAR. Their specs were not captured (PS-IDX
  rows 160-162).
- Which system receives the TIDE file. The catalog does not name it.
- Whether any successor carries the SAR-only fields: 504 (SAR-08), Title III
  (SAR-13), Exempt From Passing (SAR-06), ML Exempt From ELA (SAR-07, SAR-12),
  accountable CDS (SAR-39), and SMIDs (SAR-40). If none does, those rows survive
  only for the in-house dashboard and roster.

## Section C: Regression tests

These follow #5558 step 3. They are error-level and carry no ticketing `meta`.
They go on the defending model and on any model that rebuilds the same logic
from raw inputs. RPT-TAB and RPT-GS are views, so these tests run when the
view's SQL changes. That is when code bugs enter, so it fits their purpose.

Most SAR candidates have no safe "defend downstream" step. Dropping or rewriting
an accommodation could deny a student one. The defending model should carry a
conflict flag, not a corrected value (D-8).

| id   | model                                                                                     | test                                                                                                                                                                                             | severity        | catches                                                                                                |
| ---- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------- | ------------------------------------------------------------------------------------------------------ |
| R-01 | RPT-TAB                                                                                   | `ucc(student_number, accommodation)`                                                                                                                                                             | error           | Fan-out in the enrollment join. The model has no tests today, and every `rpt_` needs a uniqueness test |
| R-02 | RPT-GS                                                                                    | `unique(student_number)`                                                                                                                                                                         | error           | `any_value()` grouping merging a student's rows from 2 regions. The model has no tests today           |
| R-03 | RPT-GS                                                                                    | `av`: `ela_test_code` ELA03-ELA09, ELAGP; `math_test_code` MAT03-MAT08, ALG01, GEO01, ALG02, MATGP, `NO MATH COURSE ASSIGNED`; `sci_test_code` SC05, SC08, SC11                                  | error           | `concat('ELA', '0', grade_level)` producing `ELA010` if the grade filter widens                        |
| R-04 | RPT-GS                                                                                    | `eit`: `ela_test_code = if(grade_level = 11, 'ELAGP', concat('ELA0', grade_level))` where not null; the math analog for grades 3-8 with no course                                                | error           | Grade and code drift                                                                                   |
| R-05 | RPT-GS                                                                                    | `eit`: `ela_exemption_reason != 'ELA Exempt - Other' and math_exemption_reason != 'Math Exempt - Other'`                                                                                         | error           | Drift between `is_exempt_state_testing` and the reason `case`                                          |
| R-06 | RPT-GS, `int_extracts__student_enrollments_subjects`, `int_reporting__promotional_status` | After D-4, a student with `math_state_assessment_name in DLM_MATH` gets no math test code, `is_exempt_state_testing` for Math, and an `exemption` value. Project inputs where a model lacks them | error           | Today's split: `'3'` vs `'3', '4'`                                                                     |
| R-07 | RPT-GS                                                                                    | `not (asmt_exclude_ela = 1 and ela_test_code is not null)`, plus the math analog. Only if D-5 says exclusions suppress codes; the roster must first read the flags                               | error           | The roster ignoring PowerSchool exclusions                                                             |
| R-08 | RPT-TAB                                                                                   | `sing`: every region with current enrolled NJ students in ENR has rows in RPT-TAB (after D-6)                                                                                                    | error           | A region dropping out of the filter again                                                              |
| R-09 | RPT-TAB                                                                                   | `sing`: each `accommodation` has at least 1 non-null value network-wide                                                                                                                          | warn (seasonal) | Reading a dead column (D-2)                                                                            |
| R-10 | H-REG                                                                                     | `ucc(student_number, _dbt_source_project, academic_year)`; `region` `av` Newark, Camden, Paterson, plus `not_null`                                                                               | error           | Fan-out; regression in region scope                                                                    |

## Section D: Open questions

1. **Is the SAR gone for 2026-27?** The only direct evidence is an unrendered
   HTML comment in the NJSLEDS calendar that says "Confirm before publish".
   Reporting Responsibilities (September 2026) still describes SAR duties.
   PowerSchool has not moved the report to Legacy, and no release note retires
   it. To settle it:
   - ask the NJDOE assessment or NJSLEDS office, or the district test
     coordinator;
   - OCR the image-only 2026-27 Submission Timeline PDF;
   - capture the successor template specs (PS-IDX rows 160-162).
2. **Which accommodation column set is populated?** The staging contract carries
   3 sets:
   - the PS-SAR spec set (`asmt_*`, `parcc_*`);
   - the non-spec set RPT-TAB reads (`calculation_device_math_tools`,
     `parcc_text_to_speech`, `parcc_text_to_speech_math`,
     `asmt_humanreader_signer`);
   - the `sla_*` set, plus `presentation` and `embedded_co_writer_ela`.

   This gates P3, P4, and SAR-29 and SAR-31 to SAR-35. The query below (not run)
   returns only aggregates: 1 row per region and column. Small cells under 10
   stay in `#data_team` or local and never go to GitHub. `top_values` also
   answers P3, the stored "set" value.

   ```sql
   with
       current_nj as (
           select s.*,
           from `teamster-332318.kipptaf_powerschool.stg_powerschool__s_nj_stu_x` as s
           inner join
               `teamster-332318.kipptaf_extracts.int_extracts__student_enrollments` as e
               on s.studentsdcid = e.students_dcid
               and s._dbt_source_project = e._dbt_source_project
           where e.academic_year = 2026 and e.rn_year = 1 and e.enroll_status = 0
       ),

       string_cols as (
           select _dbt_source_project, column_name, column_value,
           from
               current_nj unpivot include nulls (
                   column_value for column_name in (
                       -- PS-SAR spec set
                       asmt_frequent_breaks, asmt_alternate_location,
                       asmt_small_group, asmt_special_equip, asmt_specified_area,
                       asmt_time_of_day, asmt_answer_masking, asmt_read_aloud,
                       asmt_color_contrast, asmt_asl_video, asmt_screen_reader,
                       asmt_non_screen_reader, asmt_closed_caption_ela,
                       asmt_refresh_braille_ela, asmt_alt_rep_paper,
                       parcc_large_print_paper, asmt_braille_tactile_paper,
                       asmt_human_signer, asmt_answers_recorded_paper,
                       asmt_braille_response, parcc_math_tools,
                       parcc_constructed_response_ela, asmt_selected_response_ela,
                       asmt_math_response, asmt_monitor_response,
                       asmt_word_prediction, asmt_directions_clarified,
                       asmt_directions_aloud, asmt_math_response_el,
                       parcc_translation_math_paper, asmt_dictionary,
                       asmt_text_to_speech, asmt_ih, asmt_lh, asmt_ri, asmt_rl,
                       asmt_unique_accommodation, asmt_emergency_accommodation,
                       asmt_extended_time, asmt_extended_time_math,
                       parcc_ell_paper_accom, parcc_test_format,
                       parcc_ela_test_code, parcc_math_test_code,
                       parcc_exempt_from_passing, parcc_retest,
                       state_assessment_name, math_state_assessment_name,
                       state_ell_status, pid_title3status,
                       access_tier_paper_tests, alternate_access,
                       access_test_format_override,
                       -- non-spec set read by RPT-TAB
                       calculation_device_math_tools, parcc_text_to_speech,
                       parcc_text_to_speech_math, asmt_humanreader_signer,
                       -- sla_ codes and newer fields
                       sla_test_code, sla_test_format, sla_retest,
                       sla_braille_response, sla_braille_tactile_paper,
                       sla_color_contrast, sla_constructed_response,
                       sla_directions_aloud, sla_emergency_accommodation,
                       sla_extended_time, sla_humanreader_signer,
                       sla_presentation, sla_science_response_el,
                       sla_selected_response, sla_spanish_trans,
                       sla_text_to_speech, presentation, embedded_co_writer_ela
                   )
               )
       ),

       int_cols as (
           select
               _dbt_source_project,
               column_name,
               cast(column_value as string) as column_value,
           from
               current_nj unpivot include nulls (
                   column_value for column_name in (
                       asmt_exclude_ela, asmt_exclude_math, sla_exclude_tf,
                       pid_504_tf, pid_lepexemptlal_tf,
                       sla_alt_rep_paper, sla_alternate_location,
                       sla_answer_masking, sla_answers_recorded_paper,
                       sla_asl_video, sla_closed_caption, sla_dictionary,
                       sla_directions_clarified, sla_frequent_breaks,
                       sla_human_signer, sla_large_print_paper,
                       sla_monitor_response, sla_non_screen_reader,
                       sla_read_aloud, sla_refresh_braille, sla_screen_reader,
                       sla_small_group, sla_special_equip, sla_specified_area,
                       sla_time_of_day, sla_unique_accommodation,
                       sla_word_prediction
                   )
               )
       ),

       all_cols as (
           select _dbt_source_project, column_name, column_value,
           from string_cols
           union all
           select _dbt_source_project, column_name, column_value,
           from int_cols
       )

   select
       _dbt_source_project,
       column_name,
       count(*) as n_students,
       countif(column_value is not null) as n_non_null,
       countif(column_value not in ('', '0', 'N')) as n_set,
       approx_top_count(column_value, 5) as top_values,
   from all_cols
   group by _dbt_source_project, column_name
   order by column_name, _dbt_source_project
   ```

3. **Which status source is authoritative?** This gates SAR-01 to SAR-07, SAR-13
   to SAR-17, and SAR-30.
   - IEP: EdPlan `spedlep` (ENR, `dim_student_iep_status`) or PowerSchool
     `specialed_classification`.
   - 504: `S_NJ_REN_X.pid_504_tf`, then `U_StudentsUserFields.is_504` (ENR), or
     `S_NJ_STU_X.pid_504_tf`.
   - ML: LEP dates (ENR, `dim_student_ell_status`), `state_ell_status`, or the
     Student Management field `EligibleForLIEP`.
4. **What do the State Assessment Name codes mean?** PS-SAR gives no domain. The
   in-house models use 2, 3, and 4. Does a 1 exist? Is math `'4'` DLM?
   `int_extracts__student_enrollments_subjects` and RPT-GS treat only `'3'` as
   math DLM, while `int_reporting__promotional_status` treats `'3'` and `'4'`. A
   grade 3-8 student with math `'4'` gets a math test code on the roster and
   "Exempt - Special Education" on promotional status.
5. **What do the exclude flags mean?** What do `asmt_exclude_ela`,
   `asmt_exclude_math`, and `sla_exclude_tf` mean? Should RPT-GS honor them? It
   ignores them today.
6. **Is it intentional that RPT-TAB leaves out Paterson?** RPT-GS includes
   Paterson (`region != 'Miami'`), and the staging union carries it.
7. **What shape should the host model take?** A student-by-year model duplicates
   ENR's grain (A4). The options:
   - Add the columns to ENR.
   - Build a long `_unpivot` at student by year by accommodation (RPT-TAB's
     shape moved upstream). Status and format would ride on every row, but
     column-pair checks SAR-33 to SAR-35 need a wide shape.
   - Accept a wide model as an A4 exception.

   Decide before P1.

8. **Does a flag column count as a defending step?** #5558 expects a defending
   model that handles bad rows. Accommodations have no safe automatic fix. Is a
   conflict flag column acceptable as step 2?
9. **Is current-state-only acceptable?** `s_nj_stu_x` keeps no history, so
   tickets cannot cover past years. An auto-close means only that the value
   changed.
10. **Rule confirmations from SPED and ELL:**
    - Which `SWD_COLS` need an IEP, 504, or EL plan, and which are open to all
      students (SAR-05, SAR-14)?
    - What is the ML first-year cutoff (SAR-07)?
    - Do the review lists (SAR-14, SAR-15, SAR-32) become tickets or stay on the
      dashboard?
11. **Is it intended that science extended time reads math?** RPT-GS reads
    `asmt_extended_time_math` for science extended time.
12. **How do the passing and taking exemption fields relate?** Is Exempt From
    Passing related to the Student Management pathway code `M` (SAR catalog
    Q16)? Staging also carries `iep_exemptpassinglal_tf`,
    `iep_exemptpassingmath_tf`, and `iep_exempttaking*_tf`, which PS-SAR does
    not name. Which of these is current?
13. **Do the owner categories map to #5550's `owning_role`?** TC, SPED, and ELL
    must map to it. Does it have a school testing coordinator role?
14. **Where does a test-code list come from?** The PowerSchool appendix was not
    captured, so SAR-19 to SAR-21 rely on in-house code names.

## Section F: Column population, measured 2026-10-20 (aggregate, enrolled AY2026 students, rn_year = 1)

Per-region count of students with a non-null, non-zero, non-false value; 6,558
Newark rows max. Columns absent from this table had zero populated values in
every region, which includes the spec-named `asmt_text_to_speech` and
`parcc_math_tools`.

| column                                                     |          Newark |             Camden |                           Paterson |
| ---------------------------------------------------------- | --------------: | -----------------: | ---------------------------------: |
| access_accountablecounty / district / school               |            1374 |                459 |                                  0 |
| parcc_testing_site_county / district / school              |       1373-1374 |                459 |                                  0 |
| sla_accountable_site_county                                |             153 |                 79 |                                  0 |
| sla_accountable_site_district / school, sla_testing_site_* |               0 |                 79 |                                  0 |
| state_assessment_name                                      |             548 |                341 |                                184 |
| math_state_assessment_name                                 |             359 |                234 |                                 71 |
| state_ell_status                                           |              21 |                  0 |                                184 |
| parcc_ela_test_code                                        |              92 |                188 |                                  0 |
| parcc_math_test_code                                       |              11 |                127 |                                  0 |
| parcc_test_format                                          |             241 |                 32 |                                186 |
| asmt_frequent_breaks                                       |             941 |                276 |                                 26 |
| asmt_small_group                                           |             953 |                324 |                                 32 |
| asmt_extended_time / _math                                 |       775 / 779 |          283 / 288 |                            92 / 92 |
| asmt_alternate_location                                    |             503 |                162 |                                 16 |
| asmt_specified_area                                        |             417 |                 39 |                      fewer than 10 |
| asmt_time_of_day                                           |             177 |                 69 |                      fewer than 10 |
| parcc_ell_paper_accom                                      |             339 |                102 |                                 75 |
| parcc_translation_math_paper                               |              86 |                 49 |                                 49 |
| parcc_text_to_speech / _math (Tableau set)                 |       173 / 218 |          101 / 142 |                 fewer than 10 / 20 |
| calculation_device_math_tools (Tableau set)                |             253 |                149 |                                 20 |
| asmt_humanreader_signer (Tableau set)                      |   fewer than 10 |      fewer than 10 |                                  0 |
| asmt_read_aloud                                            |              72 |      fewer than 10 |                      fewer than 10 |
| asmt_dictionary                                            |              95 |      fewer than 10 |                                 39 |
| asmt_directions_clarified / _aloud                         |         83 / 50 | 15 / fewer than 10 |                            28 / 47 |
| sla_extended_time / small_group / frequent_breaks          | 238 / 231 / 234 |       84 / 82 / 63 | 12 / fewer than 10 / fewer than 10 |
| sla_alternate_location / specified_area                    |         85 / 85 |            36 / 21 |      fewer than 10 / fewer than 10 |
| sla_text_to_speech                                         |   fewer than 10 |                 34 |                      fewer than 10 |
| sla_spanish_trans                                          |   fewer than 10 |                 12 |                      fewer than 10 |
| alternate_access                                           |               0 |                 31 |                                  0 |
| pid_title3status                                           |   fewer than 10 |                  0 |                                  0 |
| every other asmt_* / sla_* / parcc_* column                |           < 100 |               < 20 |                               < 10 |

Reading: the `asmt_*` set is the live accommodation set; the spec's
`asmt_text_to_speech` and `parcc_math_tools` names are dead and the Tableau
model's `parcc_text_to_speech(_math)` and `calculation_device_math_tools` are
the real ones; the `sla_*` science set is separately maintained. Paterson
carries no accountable or testing-site CDS codes on any student. Stored test
codes are sparse everywhere and absent in Paterson, so a test-code presence rule
would fire on nearly every in-scope student today.
