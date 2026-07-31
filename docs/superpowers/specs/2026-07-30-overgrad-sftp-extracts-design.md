# Overgrad SFTP Extracts

Refs #4649

Status: **approved** — design, stakeholder questions, and project plan are
settled. The GPA model and several field-level decisions are explicitly gated on
stakeholder answers (see _Stakeholder questions_); those gates are recorded in
the plan rather than resolved here.

## Problem

Overgrad now offers SIS Sync over SFTP for three file types: student rostering,
GPAs, and standardized test scores. Today all three are loaded by manual CSV
upload through the Overgrad web UI. We want them delivered nightly by Dagster
instead.

AP scores are in scope as a fourth file, riding on the same test-score endpoint,
limited to the five AP subjects Overgrad accepts.

### The Salesforce gate

Overgrad's `Student ID` is the **Salesforce contact id**, not `student_number`.
This is load-bearing and already established in the codebase —
`int_extracts__student_enrollments.sql:487-489` joins Overgrad on:

```sql
on e.salesforce_contact_id = ovg.external_student_id
and e._dbt_source_project = ovg._dbt_source_project
```

The second predicate is not incidental. With separate per-region Overgrad
accounts, an anti-join that omits it would treat a Newark-to-Camden transfer as
already present in Overgrad and never create them in Camden's account. Every
comparison against `int_overgrad__students` in this spec must carry the
source-project predicate.

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

| File   | Comparison available                                                                                                                                | Grain                             |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| Roster | `stg_overgrad__students.external_student_id`                                                                                                        | exact, per student                |
| GPA    | `academics__unweighted_gpa` / `academics__weighted_gpa`                                                                                             | current value only                |
| SAT    | `academics__sat_superscore`, `academics__highest_sat`, `academics__highest_psat_nmsqt`, `academics__highest_psat_10`, `academics__highest_psat_8_9` | aggregate only, not per test date |
| AP     | none                                                                                                                                                | no Overgrad-side AP data          |

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
`e.* except (...)` block. This matches the house pattern exactly —
`rpt_powerschool__autocomm_students.sql:30` is
`se._dbt_source_project as code_location`.

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

Newark and Camden have separate Overgrad accounts today, evidenced by distinct
1Password secret items per district in `dagster-cloud.yaml`:
`op-overgrad-api-kippnewark` for `kippnewark` (and `kipptaf`, which reuses the
Newark key) versus `op-overgrad-api-kippcamden` for `kippcamden`. Both items are
declared in `.k8s/1password/items.yaml`.

Two things that look like evidence for this but are not: `OVERGRAD_RESOURCE` is
a single shared object defined once at `src/teamster/core/resources.py:102` and
imported identically by all three locations, and the
`overgrad_api_limit_<code_location>` pool name is auto-derived from an f-string
at `src/teamster/libraries/overgrad/assets.py:22` — it is a Dagster concurrency
pool and would be per-location even with one shared Overgrad account.

Each account therefore needs its own SSH resource and its own initial manual
upload to establish mappings.

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
| `graduation_year` | `graduation_year`    | `yyyy`; Salesforce-backed — see below        |
| `fafsa_completed` | `has_fafsa`          | Salesforce-backed, as `autocomm` uses        |

Filters: `academic_year = current`, `rn_year = 1`, `school_level = 'HS'`, active
enrollment, and an anti-join against `int_overgrad__students` on **both**
`external_student_id` and `_dbt_source_project` — omitting the source-project
predicate would silently suppress Newark-to-Camden transfers, as described under
_The Salesforce gate_.

**This grain is provisional pending Q12.** The model is specified as one row per
student _to create_, which assumes `StudentSisFile` is create-only. If the
importer supports upsert, the anti-join is the wrong design — we would send the
full roster and let Overgrad reconcile — and that changes the model's grain, its
tests, and part of the rationale for diffing in `kipptaf` at all. Build it
upsert-shaped so the anti-join is a filter that can be dropped rather than a
structural assumption that has to be unwound.

**On `graduation_year`.** Three competing definitions exist in this repo, and
Overgrad's match algorithm keys on this field, so the choice is deliberate:

- `int_extracts__student_enrollments.graduation_year` resolves to
  `adb.graduation_year` — the Salesforce contact field
  (`base_powerschool__student_enrollments.sql:100`). **This is what we send.**
- `salesforce_graduation_year` in that same base model (line 206), derived from
  actual or expected HS graduation date.
- `rpt_powerschool__autocomm_students.sql:36` derives its own as
  `academic_year + (13 - grade_level)`.

The Salesforce-backed field is chosen for consistency with the
compare-against-Salesforce principle applied to GPA and the roster gate:
Overgrad is keyed on Salesforce contact ids, so its graduation year should come
from the same record.

Implementation note: that column's YAML `meta.source_model` claims
`stg_powerschool__studentcorefields`, which is wrong — the SQL is
`adb.graduation_year`. Pre-existing repo doc bug, not introduced here, but it
will mislead anyone tracing the lineage.

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

`scope = 'SAT'` is sufficient to keep PSAT rows out, even though
`int_assessments__college_assessment` also unions
`int_collegeboard__psat_unpivot` with its `test_type` passed straight through as
`scope`. That `test_type` is a closed `case` in `stg_collegeboard__psat.sql`
over the Dagster partition key, yielding only `PSAT NMSQT`, `PSAT 8/9`, or
`PSAT10` — never `SAT`. The only hardcoded `'SAT' as test_type` in the project
is `int_collegeboard__sat_unpivot.sql:77`.

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

Three problems, all recorded here rather than buried:

**No test date.** `int_collegeboard__ap_unpivot` carries only `admin_year`.
Overgrad requires `Test Date`. AP exams are administered in May, so the date is
synthesized as May 15 of `admin_year`. Flagged as a vendor question (Q14).

`admin_year` on this model is already a **4-digit `INT64`** — the raw College
Board field is two-digit, but the model applies
`extract(year from parse_date('%y', admin_year))` during the unpivot and derives
`academic_year` as that value minus one. So the synthesized date is
`date(admin_year, 5, 15)` with no further parsing.

**AP Physics collapses.** College Board reports Physics 1, Physics 2, Physics C:
Mechanics, and Physics C: E&M as distinct exams. Overgrad accepts exactly one
`AP Physics`. Combined with the synthesized date, a student who sat Physics 1
and Physics 2 in the same May produces two rows with identical student, test,
and date — precisely the case Overgrad rejects.

Resolution: dedupe to the **highest** `exam_grade` per
`(student_id, overgrad_test, test_date)`. The file stays valid, but a student's
second Physics exam is silently dropped. Surfaced in the stakeholder questions
(Q11).

**The College Board ID crosswalk drops students silently.**
`int_collegeboard__ap_unpivot` reaches `powerschool_student_number` by joining
`stg_google_sheets__collegeboard__ap_id_crosswalk` on `ap_number_ap_id`.
Unresolved IDs fall out with no error.

This is known and recurring, not hypothetical. A dedicated data test exists for
exactly this failure — `int_collegeboard__ap_unpivot__crosswalk_resolves`,
described at `src/dbt/kipptaf/tests/properties.yml:228-241` — whose description
states that unresolved students have their AP scores dropped. The repo also
carries a `collegeboard-ap-data-ingest-protocol` skill because these gaps keep
recurring.

`rpt_overgrad__ap_scores` inherits that path, and it is **independent of the
Salesforce gate**. Two consequences for the build:

- The AP extract needs a row-count assertion before send, not just after.
- `int_collegeboard__ap_unpivot` runs `dbt_utils.deduplicate` partitioned by
  `powerschool_student_number`, so NULL-keyed rows from a crosswalk miss
  collapse to a single row rather than failing loudly. Confirm behavior while
  building.

**Consider `int_assessments__ap_assessments` as the source instead.** It wraps
`int_collegeboard__ap_unpivot` (for `academic_year >= 2018`) and unions
Salesforce AP scores for earlier years, and critically it applies
`where powerschool_student_number is not null` — which drops exactly the
crosswalk-miss rows described above instead of letting them collapse. It exposes
`test_subject`, `ap_course_name`, and `title` for the Overgrad mapping. The
tradeoff: it does not carry `admin_year`, only `academic_year`, so the
synthesized date becomes May of `academic_year + 1`. Decision pending.

The five accepted values are mapped with an inline `case` expression rather than
by extending `stg_google_sheets__collegeboard__ap_course_crosswalk`. Five values
do not justify a sheet round-trip, and inline keeps the mapping reviewable in
the PR. If Overgrad expands the list, moving it to a sheet column is a small
follow-up.

## Stakeholder questions

Grouped by who can answer, because they unblock different work.

### GPA — blocks `rpt_overgrad__gpas` (Kyla, Diane)

- **Q1.** Which GPA goes to Overgrad: the Salesforce college match GPA
  (`college_match_display_gpa__c`), PowerSchool cumulative Y1 weighted, or
  unweighted? Placeholder in this spec is the Salesforce field.
- **Q2.** Is that value already on a 4.0 scale? Overgrad requires 4.0 and does
  not rescale.
- **Q3.** Label it `Unweighted`, `Weighted`, or send both rows? Overgrad's match
  algorithm only runs off an unweighted GPA — sending only weighted means match
  silently produces nothing for every student.
- **Q4.** What cadence? A nightly diff-and-send means off-schedule requests stop
  being requests: any change in Salesforce propagates within a day. Is that the
  goal, or does GPA need to hold steady between the Foundation's scheduled
  college-match updates so students do not see it move mid-cycle?
- **Q5.** Should GPA flow for all HS grades, or seniors only?

Q4 is the substantive one. It reframes recurring ad-hoc GPA requests as a
cadence decision rather than a ticket queue.

### Roster and scope (Kyla, Diane)

- **Q6.** Send demographics — birth date, gender, race/ethnicity? Overgrad
  accepts them and its `students` object already holds values, but adding them
  to a recurring outbound feed is a privacy decision. Default in this spec is to
  omit them.
- **Q7.** Which grade levels get rostered? This spec assumes all HS; Overgrad is
  often used for grades 11 and 12 only.
- **Q8.** Should the roster file also push updates for existing students (email
  changes, corrected graduation year), or only create new ones? See Q12 — the
  answer may be forced by Overgrad's importer.
- **Q9.** Who owns triggering welcome emails? SFTP-created accounts get none, so
  students will not know they have an account until someone tells them. This is
  the most likely way a technically successful launch still fails.
- **Q10.** Add ACT alongside SAT? Already present in
  `int_assessments__college_assessment`, and Overgrad accepts the full battery —
  near-zero marginal cost.
- **Q11.** AP Physics: Overgrad has one `AP Physics` against College Board's
  four exams. This spec keeps the highest score and drops the rest. Acceptable,
  or should Physics be excluded entirely so nothing is silently lost?

### Vendor — blocks setup (`integrations@overgrad.com`)

- **Q12.** Does the SIS Sync `StudentSisFile` mapping support upsert, or is it
  fixed to create-only? The manual importer forces a choice between "Creating"
  and "Editing" at mapping time, which suggests one SFTP mapping cannot do both.
  **This decides the shape of `rpt_overgrad__students`, not just the file
  count** — see the grain note under that model. Highest-priority vendor
  question.
- **Q13.** One SFTP account per Overgrad district, or one shared credential for
  both Newark and Camden?
- **Q14.** AP scores have no exam date in the College Board file. Is a
  synthesized May 15 acceptable, or is there a preferred convention?
- **Q15.** Digital SAT: use `New SAT Reading and Writing` or
  `New SAT Evidence-Based Reading and Writing`? Both are in the accepted list.
  Which feeds the match algorithm?
- **Q16.** Is there any delivery feedback — a processed or error file written
  back to SFTP, or an API endpoint? Today the only error surface is the History
  page in the UI, which nothing can monitor.
- **Q17.** What are the file size and row count limits, and what happens to a
  partially-invalid file?
- **Q18.** Confirm the exact subdirectory names for GPA and test-score files.
  The doc gives only `uploads/StudentSisFile/` explicitly.

Q16 is the one to push hardest on. Everything else has a workaround;
unmonitorable failure is an operational burden we would own indefinitely.

## Project plan

Target: pipeline established and tested by mid-September 2026. Plan date is
2026-07-30.

### Sequencing constraint

The manual header-mapping upload **cannot be front-loaded**. Overgrad requires
SFTP files to use the same headers as the manual upload that established the
mapping, so the sample CSV must be generated from the finished dbt models.
Mapping headers before the models are final means renaming them afterward, which
breaks the sync silently.

Dependency order: models → sample CSV → manual mapping → SFTP enabled.

The credential request is the one item that can be front-loaded, and it sits on
the critical path from day one with a turnaround we do not control. It goes
first.

### Milestones

| Week         | Work                                                                                                                                                                                                   | Gates                                                                                    |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| Aug 3–7      | Email `integrations@overgrad.com` for SFTP credentials on both accounts, with Q12–Q18 attached. Hold the GPA and roster-scope meeting. Record decisions in this spec.                                  | none                                                                                     |
| Aug 10–21    | Build 4 network models and 8 district passthroughs. One PR per file type. `rpt_overgrad__gpas` waits on Q1–Q5. `rpt_overgrad__students` is built upsert-shaped so Q12 changes a filter, not the grain. | GPA model gated on stakeholder answers; roster de-risked against Q12 rather than blocked |
| Aug 24–28    | Generate sample CSVs from the built models. Manual upload of each file type in both accounts to establish header and value mappings — 8 uploads.                                                       | models merged; credentials received                                                      |
| Aug 31–Sep 4 | Dagster wiring: SSH resources per code location, `config/overgrad.yaml`, assets, jobs, schedules at `0 4 * * *`. Dry-run extracts to `couchdrop` instead of Overgrad, inspect CSVs.                    | dry run needs no vendor involvement                                                      |
| Sep 7–11     | Flip destination to Overgrad. Live send on a small subset, verify against the Overgrad History page, then full send. Confirm row counts and spot-check students in the UI.                             | mappings established                                                                     |
| Sep 14–15    | Monitor a full week of nightly runs. Hand off welcome-email ownership. Update docs. File follow-up issues.                                                                                             | target met                                                                               |

The dry-run-to-`couchdrop` step is worth the extra day. It shows exactly what
Overgrad would receive — headers, date formats, the AP Physics dedupe, row
counts — with no vendor-visible action and no bad load to unwind.

### Asana structure

Parent task `#4649 | feat: build Overgrad SFTP extracts` in the TEAMster
project, Type = `Issue`, with subtasks per milestone. PR-level subtasks are
added as PRs open, Type = `Pull Request`.

15 subtasks: 2 for week one, 4 model tasks, 1 mapping-upload task per account
(2), 2 Dagster tasks, 3 test and validation tasks, 2 handoff tasks. Due dates
set to the week boundaries above.

### Schedule risks

- **Vendor turnaround is the top risk.** Credentials plus answers to seven
  questions from a vendor whose support hours are 7am–9pm CST. A two-week
  turnaround makes mid-September tight, which is why the request goes out in
  week one rather than after the models are built.
- **No machine-readable error surface** (Q16). Until answered, "tested" must
  include a human checking the Overgrad History page, and steady-state operation
  carries a monitoring gap.
- **The GPA decision gates one model but could reshape it.** If the answer to Q4
  is a cadence other than "nightly whenever Salesforce changes",
  `rpt_overgrad__gpas` needs different logic, not just a different column.
- **Q12 shapes the roster model.** Mitigated by building upsert-shaped rather
  than blocking, but a late "create-only" answer still means re-testing the
  roster file.
- **The College Board ID crosswalk silently drops AP students**, independent of
  the Salesforce gate. A recurring, known failure with its own data test
  (`int_collegeboard__ap_unpivot__crosswalk_resolves`) and its own repo skill.
  The AP send needs a row-count assertion, and crosswalk gaps must be cleared
  before the September validation window or AP coverage will look complete while
  being partial.

Schools open in late August, so new-student Salesforce contact ids will still be
settling during the September test window. This is realistic timing rather than
a defect, but it does mean the first full send will not cover every enrolled
student — stakeholders should hear that as expected behavior, not a bug.

## Follow-ups

- Test-score idempotency: replace full resend with a ledger of sent rows if
  Overgrad rejects duplicate submissions. Tracked as a separate issue.
- Welcome emails are not sent for SFTP-created accounts. Someone owns triggering
  them; this is a process gap, not a code gap.
- ACT scores are already in `int_assessments__college_assessment` and Overgrad
  accepts the full ACT battery. Adding them would be low marginal cost.
