# Survey Domain Implementation Plan

**Goal:** Build the survey domain — dimensions for survey instruments,
administration windows, questions, and respondent expectations, a bridge table
for the survey-to-question many-to-many relationship, and two fact tables for
submission events and individual question responses.

**Architecture:** `dim_surveys` is the instrument-level reference (no temporal
scoping). `dim_survey_administrations` is the instrument x term instance, FK to
both `dim_surveys` and `dim_terms`. `dim_survey_questions` is a pure reference
dimension — questions are reused across surveys, so the survey-to-question
pairing lives in `bridge_survey_questions`. `dim_survey_expectations` scaffolds
expected respondents per administration. `fct_survey_submissions` records
completion events; `fct_survey_responses` records per-question answers.

**Tech Stack:** dbt (BigQuery dialect), `dbt_utils.generate_surrogate_key()`,
`dbt_utils.deduplicate()`, Google Forms and Alchemer sources.

**Spec reference:**
`docs/superpowers/specs/2026-03-27-star-schema-data-mart-design.md` — Survey
Domain section.

**Dependencies:** Plan 1 (Conformed Dimensions), Plan 3 (Staff Domain for
dim_staff), Plan 2 (Student Domain for dim_student_enrollments and
dim_student_contact_persons).

---

## Prerequisites

- Working directory:
  `/workspaces/teamster/.worktrees/cbini/feat/claude-star-schema-data-mart/`
- All file paths relative to `src/dbt/kipptaf/`

## Task Overview

| Task | Model                        | Type   | Dependencies |
| ---- | ---------------------------- | ------ | ------------ |
| 1    | `dim_surveys`                | dim    | none         |
| 2    | `dim_survey_questions`       | dim    | none         |
| 3    | `bridge_survey_questions`    | bridge | Tasks 1, 2   |
| 4    | `dim_survey_administrations` | dim    | Task 1       |
| 5    | `dim_survey_expectations`    | dim    | Task 4       |
| 6    | `fct_survey_submissions`     | fact   | Task 4       |
| 7    | `fct_survey_responses`       | fact   | Tasks 2, 6   |

---

### Task 1: `dim_surveys`

**Files:**

- `models/marts/dimensions/dim_surveys.sql`
- `models/marts/dimensions/properties/dim_surveys.yml`

**Spec grain:** One row per survey instrument. No temporal scoping — stable
instrument-level attributes only.

**Key:** `survey_key` = `generate_surrogate_key(["survey_id"])`.

**Upstream:**

- `int_google_forms__form_responses` (Google Forms instruments, DISTINCT)
- `source("alchemer", "base_alchemer__survey_results")` (Alchemer, DISTINCT)
- Hardcoded synthetic IDs for archived Alchemer surveys and PowerSchool Family
  survey

`survey_type` and `subject_area` are derived from `survey_name` via CASE
statements mapping known survey names to classification buckets. `platform` is
derived similarly (Google Forms, Alchemer, or PowerSchool).

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 2: `dim_survey_questions`

**Files:**

- `models/marts/dimensions/dim_survey_questions.sql`
- `models/marts/dimensions/properties/dim_survey_questions.yml`

**Spec grain:** One row per distinct question shortname. Questions are reused
across surveys; grain is `question_shortname` (not `question_id`, because Google
Forms grid sub-questions share a `question_id`).

**Key:** `survey_question_key` =
`generate_surrogate_key(["question_shortname"])`.

**Upstream:**

- `int_google_forms__form_responses` (item_abbreviation as shortname)
- `stg_google_sheets__surveys__scd_question_crosswalk` (SCD scale items with
  `question_code LIKE 'School_Survey_%'`)

`dbt_utils.deduplicate()` on `question_shortname`, ordered by
`question_text asc`.

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 3: `bridge_survey_questions`

**Files:**

- `models/marts/bridges/bridge_survey_questions.sql`
- `models/marts/bridges/properties/bridge_survey_questions.yml`

**Spec grain:** One row per survey x question_shortname pair at the instrument
definition level (not the administration instance).

**Key:** `survey_question_bridge_key` =
`generate_surrogate_key(["survey_id", "question_shortname"])`.

**FKs:**

- `survey_key` → `dim_surveys`
- `survey_question_key` → `dim_survey_questions`

**Upstream:**

- `int_google_forms__form_responses` (form_id + item_abbreviation pairs,
  DISTINCT)
- `stg_google_sheets__surveys__scd_question_crosswalk` (PowerSchool synthetic
  survey + SCD question codes)

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 4: `dim_survey_administrations`

**Files:**

- `models/marts/dimensions/dim_survey_administrations.sql`
- `models/marts/dimensions/properties/dim_survey_administrations.yml`

**Spec grain:** One row per survey x term combination (instrument x
administration window).

**Key:** `survey_administration_key` =
`generate_surrogate_key(["survey_id", "term_type", "term_code", "term_name", "term_start_date", "region", "school_id"])`.

**FKs:**

- `survey_key` → `dim_surveys`
- `term_key` → `dim_terms`

**Upstream:**

- `int_surveys__survey_responses` (staff, student, and family SCD submissions
  joined to reporting terms)
- `int_surveys__manager_survey_details` (manager survey campaigns)
- `source("surveys", "int_surveys__response_identifiers")` + support survey
  terms

All three branches are unioned and deduplicated via `GROUP BY`.
`administration_status` is computed as open/closed/upcoming from `term_end_date`
vs current date.

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 5: `dim_survey_expectations`

**Files:**

- `models/marts/dimensions/dim_survey_expectations.sql`
- `models/marts/dimensions/properties/dim_survey_expectations.yml`

**Spec grain:** One row per respondent x survey_administration. The
`respondent_population` discriminator determines which respondent FK is
populated (exactly one per row).

**Key:** `survey_expectation_key` =
`generate_surrogate_key(["survey_administration_key", "respondent_population", "staff_key", "student_enrollment_key", "student_contact_person_key"])`.

**FKs:**

- `survey_administration_key` → `dim_survey_administrations`
- `staff_key` → `dim_staff` (staff respondents)
- `student_enrollment_key` → `dim_student_enrollments` (student respondents,
  grades 3-12)
- `student_contact_person_key` → `dim_student_contact_persons` (family
  respondents)

Five population branches are unioned: staff SCD, staff manager, staff support,
student SCD (grades 3–12), family SCD (cross join to all contact persons).

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 6: `fct_survey_submissions`

**Files:**

- `models/marts/facts/fct_survey_submissions.sql`
- `models/marts/facts/properties/fct_survey_submissions.yml`

**Spec grain:** One row per respondent x survey_administration. Records survey
completion events across staff, student, and family populations.

**Key:** `survey_submission_key` — surrogate from survey_id + survey_response_id

- respondent identifier (varies by population).

**FKs:**

- `survey_administration_key` → `dim_survey_administrations`
- `date_submitted_key` → `dim_dates` (role-playing)
- `staff_key` → `dim_staff` (staff respondents)
- `student_enrollment_key` → `dim_student_enrollments` (student respondents)
- `student_contact_person_key` → `dim_student_contact_persons` (family
  respondents)
- `subject_staff_key` → `dim_staff` (role-playing; populated only for Manager
  Survey — identifies the manager being evaluated)

Three branches (staff/manager, student, family) are unioned.
`respondent_population` discriminator drives which FK is populated per row.

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

### Task 7: `fct_survey_responses`

**Files:**

- `models/marts/facts/fct_survey_responses.sql`
- `models/marts/facts/properties/fct_survey_responses.yml`

**Spec grain:** One row per submission x question.

**Key:** `survey_response_key` =
`generate_surrogate_key(["survey_id", "survey_response_id", "respondent_identifier", "question_shortname"])`.

**FKs:**

- `survey_submission_key` → `fct_survey_submissions`
- `survey_question_key` → `dim_survey_questions`

**Note:** This model reaches `dim_surveys` only via the chain: response →
submission → administration → survey (no direct FK to `dim_surveys`).

**Upstream:**

- `int_surveys__survey_responses` (general: SCD staff, student, family, and
  engagement surveys)
- `int_surveys__manager_survey_details` (manager survey question/answer rows)

`dbt_utils.deduplicate()` deduplicates on
`(survey_id, survey_response_id, respondent_identifier, question_shortname)`,
ordered by `response_text asc`.

- [x] **Step 1: Write YAML contract**
- [x] **Step 2: Write SQL model**
- [x] **Step 3: Build and test**
- [x] **Step 4: Commit**

---

## Verification checklist

- [x] `bridge_survey_questions` FKs both to `dim_surveys` and
      `dim_survey_questions`
- [x] `dim_survey_expectations.respondent_population` has an accepted_values
      test (staff, student, family)
- [x] `fct_survey_submissions.respondent_population` has an accepted_values test
- [x] `survey_submission_key` derivation in `fct_survey_responses` matches
      `fct_survey_submissions`
- [x] `survey_administration_key` derivation in `fct_survey_submissions` matches
      `dim_survey_administrations`
- [x] All uniqueness tests pass on primary keys
