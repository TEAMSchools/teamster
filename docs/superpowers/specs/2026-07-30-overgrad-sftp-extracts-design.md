# Overgrad SFTP Extracts

Refs #4649

Status: **in progress** — sections 1 and 2 are approved. Sections 3 (stakeholder
questions) and 4 (project plan) are pending and will be appended before this
spec goes to implementation.

## Problem

Overgrad now offers SIS Sync over SFTP for three file types: student rostering,
GPAs, and standardized test scores. Today all three are loaded by manual CSV
upload through the Overgrad web UI. We want them delivered nightly by Dagster
instead.

AP scores are in scope as a fourth file, riding on the same test-score endpoint,
limited to the five AP subjects Overgrad accepts.

### The Salesforce gate

Overgrad's `Student ID` is the **Salesforce contact id**, not `student_number`.
This is load-bearing and already established in the codebase:
`int_extracts__student_enrollments` joins Overgrad on
`e.salesforce_contact_id = ovg.external_student_id`.

The consequence for stakeholders: a student cannot be sent to Overgrad until the
KIPP Foundation has rostered them into Salesforce and a contact id exists. This
is not a same-night turnaround from enrollment. A student who enrolls Monday
does not appear in Overgrad Tuesday morning — they appear after the Salesforce
pipeline assigns them a contact id. Sending them earlier would create an
Overgrad account with no stable identifier, and their data would diverge between
the two systems with no way to reconcile it.

The rostering extract therefore filters on `salesforce_id is not null`.

### What Overgrad can and cannot tell us

The Overgrad API assets we ingest are `students`, `custom_fields`, `admissions`,
`followings`, and `universities`. There is **no** test-score or GPA endpoint. So
"what is already in Overgrad" is available at these grains:

| File   | Comparison available                                         | Grain                             |
| ------ | ------------------------------------------------------------ | --------------------------------- |
| Roster | `stg_overgrad__students.external_student_id`                 | exact, per student                |
| GPA    | `academics__unweighted_gpa` / `academics__weighted_gpa`      | current value only                |
| SAT    | `academics__highest_sat`, `sat_superscore`, `highest_psat_*` | aggregate only, not per test date |
| AP     | none                                                         | no Overgrad-side AP data          |

Roster and GPA can be diffed precisely. Test scores cannot.

### Vendor constraints from the file spec

From `Overgrad: Account, Data, and IT Set-up`:

- Only students, national test scores, and GPAs can be synced. Courses and
  course registrations cannot.
- A **manual upload of each file type must happen first** to establish the
  header and value mappings. SFTP files are rejected until that is done.
- Files go in per-type subdirectories, e.g. `uploads/StudentSisFile/`.
- Files must be sent whole — no resumed or chunked transfers.
- **Welcome emails are not sent** when accounts are created over SFTP. Students
  will not be notified; someone has to trigger welcome emails separately.
- Preferred transfer window is **4am to 6am ET**. Overgrad processes files
  immediately on receipt.
- GPA upload **replaces** the existing GPA of the same type.
- Test scores are **added** to the student's records, and Overgrad computes a
  superscore. Two scores for the same test on the same day are rejected.

Note the doc contradicts itself on test-score re-sends: the upload section says
an existing record for a particular test score "will be overwritten by the most
recently uploaded data," while the update section says you "cannot add two of
the same test type taken on the same day." This ambiguity is why idempotency is
called out as a follow-up below.

## Design

### Layering

Diff logic lives in the `kipptaf` network models. Each `rpt_overgrad__*` model
in `kipptaf_extracts` carries a `code_location` column and performs the
anti-join or value comparison against Overgrad. District models are thin
passthroughs:

```sql
select <columns>
from {{ source("kipptaf_extracts", "rpt_overgrad__students") }}
where code_location = '{{ project_name }}'
```

This follows the existing `rpt_powerschool__autocomm_students` pattern. The
alternative — diffing inside each district project against its own `overgrad`
staging models — halves join depth but duplicates the comparison logic twice per
file type, giving eight places to keep in sync instead of four.

`code_location` comes from `_dbt_source_project`, which
`int_extracts__student_enrollments` already passes through via its
`e.* except (...)` block. This is cleaner than the `regexp_extract` on
`_dbt_source_relation` that `rpt_powerschool__autocomm_students` uses.

### Model inventory

Four network models in `kipptaf_extracts`, plus eight thin district passthroughs
(four each for `kippnewark` and `kippcamden`).

| `kipptaf` model             | Grain                            | Primary source                        | Overgrad comparison                       |
| --------------------------- | -------------------------------- | ------------------------------------- | ----------------------------------------- |
| `rpt_overgrad__students`    | one row per student to create    | `int_extracts__student_enrollments`   | anti-join `external_student_id`           |
| `rpt_overgrad__gpas`        | one row per student per GPA type | `int_extracts__student_enrollments`   | value-compare `academics__unweighted_gpa` |
| `rpt_overgrad__test_scores` | one row per student, test, date  | `int_assessments__college_assessment` | none, full resend                         |
| `rpt_overgrad__ap_scores`   | one row per student, exam, year  | `int_collegeboard__ap_unpivot`        | none, full resend                         |

### Dagster wiring

Mirrors `src/teamster/code_locations/kippnewark/extracts/`. Each district code
location gets a `config/overgrad.yaml` with four asset entries, built by
`build_bigquery_query_sftp_asset()`, plus entries in `jobs.py` and
`schedules.py`.

Newark and Camden have separate Overgrad accounts today, evidenced by separate
API keys (`pool="overgrad_api_limit_kippnewark"`, and a distinct
`OVERGRAD_RESOURCE` per code location). Each therefore needs its own SSH
resource and its own initial manual upload to establish mappings.

Schedule at `0 4 * * *` in `LOCAL_TIMEZONE`, which lands inside Overgrad's
stated 4am to 6am ET processing window. Most extracts in this repo run
`0 3 * * *`; that would arrive before the window opens.

### Field mappings

Two structural facts shape all four files.

**Value mapping is server-side.** Overgrad's "Map Values" step is configured
once during the initial manual upload and stored on their account. We send
native KTAF values and Overgrad translates them. So no school-name crosswalk is
needed in dbt. The risk is inverted: our values must be **stable**, because a
renamed school silently drops out of their stored mapping rather than raising an
error.

**Column names are a contract.** Our dbt column names become the CSV headers,
and the spec requires SFTP files to use the same headers as the manual upload.
Renaming a column in a district model breaks the sync silently. The
`+contract: enforced: true` already configured on district `extracts` models is
doing real work here.

#### `rpt_overgrad__students`

| CSV header        | Source column        | Notes                                        |
| ----------------- | -------------------- | -------------------------------------------- |
| `student_id`      | `salesforce_id`      | `where salesforce_id is not null` — the gate |
| `email`           | `student_email`      | required to create the account               |
| `first_name`      | `student_first_name` |                                              |
| `last_name`       | `student_last_name`  |                                              |
| `high_school`     | `school`             | abbreviation; stable across rebrands         |
| `graduation_year` | `graduation_year`    | `yyyy`                                       |
| `fafsa_completed` | `has_fafsa`          | Salesforce-backed, as `autocomm` uses        |

Filters: `academic_year = current`, `rn_year = 1`, `school_level = 'HS'`, active
enrollment, and an anti-join against
`int_overgrad__students.external_student_id`.

Birth date, gender, and race/ethnicity are **excluded from phase 1** even though
Overgrad accepts them and their `students` object already holds values. These
are FERPA indirect identifiers, and adding them to a recurring outbound feed is
a deliberate decision, not a default. Deferred to the stakeholder questions.

#### `rpt_overgrad__gpas`

| CSV header    | Source                 |
| ------------- | ---------------------- |
| `student_id`  | `salesforce_id`        |
| `high_school` | `school`               |
| `gpa_type`    | literal `'Unweighted'` |
| `gpa`         | `college_match_gpa`    |

Sent only when `college_match_gpa` differs from
`int_overgrad__students.academics__unweighted_gpa`, or the Overgrad value is
null.

`college_match_gpa` is `int_extracts__student_enrollments`'
`salesforce_contact_college_match_display_gpa`, sourced from the Salesforce
contact field `college_match_display_gpa__c`. It is labeled `Unweighted` in
Overgrad because the spec states the match algorithm requires an unweighted GPA.

**Assumption pending Kyla and Diane.** Both the source field and the type label
need confirmation, as does whether the value is already on a 4.0 scale. This is
the model most likely to change after stakeholder input.

#### `rpt_overgrad__test_scores`

From `int_assessments__college_assessment` where `scope = 'SAT'`, joined to
`int_extracts__student_enrollments` for `salesforce_id` and `school`.

| `score_type`      | Overgrad `test`                              |
| ----------------- | -------------------------------------------- |
| `sat_total_score` | `New SAT`                                    |
| `sat_ebrw`        | `New SAT Evidence-Based Reading and Writing` |
| `sat_math`        | `New SAT Math`                               |

Excludes the legacy `sat_reading_test_score` and `sat_math_test_score` types,
the same exclusion `rpt_gsheets__college_assessments_long` applies.

SAT comes from Salesforce via `int_kippadb__standardized_test_unpivot`, which is
what `int_assessments__college_assessment` already unions for
`scope in ('ACT', 'SAT')`. This keeps the extract consistent with the "compare
against Salesforce" principle used for GPA.

**Full resend every run**, per decision. A `TODO` and a follow-up issue will
track moving to a sent-row ledger if Overgrad rejects duplicates in practice.

#### `rpt_overgrad__ap_scores`

From `int_collegeboard__ap_unpivot`, joined through
`int_extracts__student_enrollments` on `powerschool_student_number` to reach
`salesforce_id` and `school`.

Two problems, both requiring a decision that is recorded here rather than
buried:

**No test date.** `int_collegeboard__ap_unpivot` carries only `admin_year`, a
two-digit year parsed from the College Board file. Overgrad requires
`Test Date`. AP exams are administered in May, so the date is synthesized as May
15 of `admin_year`. Flagged as a vendor question.

**AP Physics collapses.** College Board reports Physics 1, Physics 2, Physics C:
Mechanics, and Physics C: E&M as distinct exams. Overgrad accepts exactly one
`AP Physics`. Combined with the synthesized date, a student who sat Physics 1
and Physics 2 in the same May produces two rows with identical student, test,
and date — precisely the case Overgrad rejects.

Resolution: dedupe to the **highest** `exam_grade` per
`(student_id, overgrad_test, test_date)`. The file stays valid, but a student's
second Physics exam is silently dropped. Surfaced in the stakeholder questions.

The five accepted values are mapped with an inline `case` expression rather than
by extending `stg_google_sheets__collegeboard__ap_course_crosswalk`. Five values
do not justify a sheet round-trip, and inline keeps the mapping reviewable in
the PR. If Overgrad expands the list, moving it to a sheet column is a small
follow-up.

## Follow-ups

- Test-score idempotency: replace full resend with a ledger of sent rows if
  Overgrad rejects duplicate submissions. Tracked as a separate issue.
- Welcome emails are not sent for SFTP-created accounts. Someone owns triggering
  them; this is a process gap, not a code gap.
- ACT scores are already in `int_assessments__college_assessment` and Overgrad
  accepts the full ACT battery. Adding them would be low marginal cost.

## Sections pending

- Section 3: stakeholder questions for Kyla, Diane, and Overgrad integrations.
- Section 4: Asana project plan culminating in a tested pipeline by
  mid-September 2026.
