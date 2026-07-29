# ParentSquare (KIPP Newark) Outbound Extracts — Design

- **Issue:** [#4480](https://github.com/TEAMSchools/teamster/issues/4480)
- **Asana:** Summer 2027 : SIS Portfolio, task 1216377560708697 (Rebuild Student
  Contacts)
- **Sources of truth:** KIPP NJ + ParentSquare Integration Planner (Google Doc);
  ParentSquare "SFTP Integration" spec (help-center PDF, updated 2026-03-18,
  attached to the Asana task)
- **Status:** design
- **Author:** Data Team

## Context

ParentSquare is a family-communications platform. For KIPP Newark it will be
used for **regional mass/emergency communication** to all Newark families (snow
days, emergencies, etc.). Individual schools continue to use DeansList for their
own mass comms — ParentSquare is the regional layer, not a school-messaging
replacement.

It needs a recurring roster feed from the warehouse so the right families and
students are reachable. This is a net-new outbound extract set (no ParentSquare
code exists in the repo) built on the established BigQuery-to-SFTP extract
pattern (`build_bigquery_query_sftp_asset`), the same one behind Clever and the
PowerSchool `autocomm` feeds.

**Scope is KIPP Newark only** for this phase. The Asana task is titled "(NJ)"
and an earlier draft of this spec assumed a network-wide NJ feed, but the
Integration Planner resolves scope to **all Newark schools only** — Camden and
Paterson are not in this phase. Student contacts are sourced from **Finalsite**
(this is the "Rebuild Student Contacts" successor to the Finalsite contact
workstream).

## Goals

- A Newark ParentSquare feed delivering the four files ParentSquare needs for
  regional comms: `schools`, `students`, `parents`, `emergency_contacts`.
- Contacts sourced from Finalsite (Household 1 parents + emergency contacts),
  with stable, mutually consistent record keys across files.
- Build everything that does not depend on the SFTP-credentials blocker now, and
  reconcile once credentials land.

## Non-goals

- **Attendance** — explicitly excluded by the Integration Planner (this is not
  an attendance-notification deployment).
- **Staff (`staff.csv`)** — deferred to a later phase. Phase-1 users are ~6
  named regional Operations leaders, provisioned by the Tech team (Google /
  Okta), not via a roster file. When added later, staff attach to a district
  office (`school_id = 0`).
- **Sections / rosters / terms** — no teacher-classroom rostering. The Planner
  sets granularity at school + grade level only.
- **Parent / student logins** — none needed.
- **Camden, Paterson, Miami** — out of scope for this phase.
- A reusable cross-tool contacts abstraction layer — YAGNI.

## Approach

Follow the Clever precedent. A set of `rpt_parentsquare__*` reporting views in
the `kipptaf` dbt project, filtered to Newark, each serialized to a CSV and
pushed to a new `parentsquare` SFTP destination by the generic extract factory.
Files are full snapshots each run; ParentSquare reconciles adds/changes/removals
on its side (its docs note attendance/data diffs are handled automatically, and
the roster files are re-read each sync).

## Components

1. **dbt models** — `src/dbt/kipptaf/models/extracts/parentsquare/`, one
   `rpt_parentsquare__<file>.sql` (schools, students, parents,
   emergency_contacts) plus a `properties/` YAML with contract + uniqueness
   tests. Land in `kipptaf_extracts` (view, contract-enforced by directory
   default).

1. **Extract config** —
   `src/teamster/code_locations/kipptaf/extracts/config/parentsquare.yaml`, one
   asset block per file, wired in `kipptaf/extracts/assets.py` with
   `destination_config={"name": "parentsquare"}` (the `clever_extract_assets`
   list-comprehension pattern). File stems must be the exact ParentSquare names
   (`schools`, `students`, `parents`, `emergency_contacts`), suffix `csv`,
   header row on.

1. **Destination resource** — `SSH_PARENTSQUARE` (`SSHResource`, host
   `sftp3.parentsquare.com`) in `src/teamster/core/resources.py`, wired as
   `ssh_parentsquare` into `kipptaf/definitions.py`; username + password (or SSH
   key) env vars in `dagster-cloud.yaml` server and run-pod blocks. Credentials
   come from the SFTP blocker below.

1. **Job + schedule** — `kipptaf__extracts__parentsquare__asset_job` in
   `extracts/jobs.py`, plus a daily `ScheduleDefinition` in
   `extracts/schedules.py`. ParentSquare recommends sending in the **early
   evening**, so schedule ~6-7pm ET (not the 3am roster slot). Shipped paused
   until the round-trip is verified.

1. **Exposure** — dbt exposure in `src/dbt/kipptaf/models/exposures/`.

## Data flow

Each model reads existing network models, filters to Newark
(`_dbt_source_project = 'kippnewark'` /
`_dbt_source_relation like '%kippnewark%'`), and projects the ParentSquare
columns.

| File                 | Source                                                                                 | Key                                                                         |
| -------------------- | -------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `schools`            | `stg_powerschool__schools` (Newark; `state_excludefromreporting = 0`)                  | `school_id = school_number`                                                 |
| `students`           | `int_extracts__student_enrollments` (Newark, current academic year, active enrollment) | `student_id = student_number`                                               |
| `parents`            | `int_students__contacts` where `contact_slot in ('contact_1', 'contact_2')`            | linked by `student_id`; no `parent_id`                                      |
| `emergency_contacts` | `int_students__contacts` where `contact_slot like 'emergency_%'`                       | `contact_id = generate_surrogate_key([finalsite_contact_id, contact_slot])` |

### Contacts sourcing (Finalsite)

`int_students__contacts` is the unified long contacts model, one row per
`(student, contact_slot)`. Newark contacts resolve through its **Finalsite**
branch, so `finalsite_contact_id`, `is_household_member`, and `is_emergency` are
populated. It exposes `contact_name`, `relationship`, `email_current`,
`phone_mobile/home/daytime/work/primary`, and `address_home`.

- **`parents.csv`** = the household parent slots `contact_1` + `contact_2`
  (Planner: "Finalsite Household 1 AND Parent 1 AND Parent 2"). One row per
  parent; the format supports more than two if a household ever has them.
  ParentSquare requires **email OR mobile** per parent — drop rows with neither.
- **`emergency_contacts.csv`** = the `emergency_1`..`emergency_4` slots. Because
  these are scalar custom fields hanging off one Finalsite contact record,
  `finalsite_contact_id` repeats across a student's emergency slots — so the
  required `contact_id` is
  `generate_surrogate_key([finalsite_contact_id, contact_slot])`, unique per
  (student, emergency ordinal). Requires **email OR phone**; emergency contacts
  receive only Smart/Urgent Alerts and get no ParentSquare account.

### ID consistency and formatting

Keys are SIS-native and consistent across files: `student_id = student_number`,
`school_id = school_number`. Per the ParentSquare spec, IDs must be one
continuous string, no spaces, and `school_id` allows no spaces/underscores/
periods; all fields ingest as strings; header names must match exactly
(underscores, no spaces/dashes); phones are 10 digits.

`grade_level` must map to ParentSquare's **-4..12** scale (K = 0, PreK1 = -4,
PreK2 = -3, Junior K = -2, Transitional K = -1). A mapping from our
`grade_level` (esp. Newark PreK codes) is required — see open question 4.

## File specs (from the ParentSquare SFTP PDF)

Only the four in-scope files. `Yes*` = one of email/phone required.

- **`schools.csv`** — `school_id`, `school_name`, `school_zip`,
  `school_address`, `school_city`, `school_state`, `principal_first_name`,
  `principal_last_name`, `principal_email`, `school_phone` (all required).
- **`students.csv`** — required: `school_id`, `student_id`, `first_name`,
  `last_name`, `grade_level`. Optional: `state_student_id`, `status` (1 =
  active, 0 = incoming), `student_email`, `cellphone` (10 digits).
- **`parents.csv`** — required: `school_id`, `student_id`, `first_name`,
  `last_name`, and email OR mobile. Optional: `parent_id` (unused),
  `relationship`, `language`, `secondary_phone`.
- **`emergency_contacts.csv`** — required: `school_id`, `student_id`,
  `contact_id`, `first_name`, `last_name`, and email OR phone.

## Delivery

- Server `sftp3.parentsquare.com`, **district-level single connection** (one set
  of files covering all Newark schools). Password or SSH key — created in the
  ParentSquare admin UI, which issues the username.
- Header row required; exact ParentSquare filenames; CSV; all values strings.
- Send in the early evening; the schedule ships paused until verified.
- Firewall note: if outbound SFTP is IP-restricted, ParentSquare's egress IPs
  are documented in the spec (not expected to matter for Dagster's egress).

## Sequencing around the blocker

1. **Phase 0 — now, unblocked.** Build the four `rpt_parentsquare__*` models
   with properties/tests, the `parentsquare.yaml` config, the `ssh_parentsquare`
   resource class, `dagster-cloud.yaml` env-var entries (names/placeholders, no
   secret values), the exposure, and the paused job + schedule. Validate model
   SQL and the asset graph in a branch deployment against `teamster-test`.

1. **Blocker — SFTP credentials.** Per the Planner this is pending (covered in a
   Monday meeting; the team needs app access first). Set up SFTP credentials in
   ParentSquare, capture the issued username, populate `dagster-cloud.yaml`
   secrets, confirm the upload path, and verify a one-file round-trip before
   sending all four.

1. **Phase Final.** Un-pause the schedule, confirm ParentSquare ingests the
   files cleanly, hand off to Ops.

1. **Phase 2 (later).** `staff.csv` (`school_id = 0`) for the regional Ops
   leaders, if not fully handled by in-app Google/Okta provisioning.

## Open questions

1. **Newark-only phase 1** — confirmed by the Integration Planner; flagging
   because it overrides the task's "(NJ)" title. (Issue #4480 corrected to
   match.)
1. **Reduced file set** — ParentSquare's generic spec lists
   `students`/`schools`/`parents`/`staff`/`sections`/`rosters` as "required".
   Confirm with ParentSquare that the comms-only 4-file set (no staff/sections/
   rosters/terms) syncs cleanly.
1. **SFTP credentials + upload path** — pending app access; also confirm whether
   files land at the SFTP root or a subdirectory.
1. **`grade_level` mapping** — exact mapping from our `grade_level` to
   ParentSquare's -4..12, especially Newark PreK codes.
1. **Parents scope** — `contact_1` + `contact_2` (Household 1 parents). Confirm
   two household parents is sufficient vs. all household members.
1. **Staff phase 2** — whether the ~6 Ops leaders ever need `staff.csv`
   (`school_id = 0`) or are fully managed in-app.

## Testing and validation

- **dbt:** contract enforcement + a uniqueness test per model (`school_id` for
  schools; `student_id` for students; a `(student_id, contact_slot)` or
  `contact_id` combination for the contact files). Validate row counts and key
  uniqueness against prod via the BigQuery MCP; confirm every emergency row has
  a non-null `contact_id` and each contact row has email or phone.
- **Asset graph:** targeted import / `dagster definitions validate` for the
  extended `kipptaf` extracts wiring.
- **Round-trip:** in a branch deployment, deliver one file to the ParentSquare
  SFTP first, confirm it lands and parses, then enable all four.
- **Vendor ingest:** with Ops, confirm ParentSquare ingests each file without
  id/match errors before un-pausing.

## PII

These files carry student and guardian PII (names, contact info). Delivery is
SFTP-to-vendor only; no PII values go to the issue, PR, Asana, or any external
surface, and validation output stays local. Tag PII columns per the repo's
`config.meta.contains_pii` convention.

## References

- Extract factory: `src/teamster/libraries/extracts/assets.py` (+ its
  CLAUDE.md).
- Clever analog: `src/dbt/kipptaf/models/extracts/clever/rpt_clever__*.sql`;
  config `.../extracts/config/clever.yaml`.
- Contacts source: `int_students__contacts` (Finalsite branch),
  `int_finalsite__student_contacts`, `int_finalsite__contact_id_attributes`.
- Destination-resource pattern: `SSH_*` resources in
  `src/teamster/core/resources.py`.
