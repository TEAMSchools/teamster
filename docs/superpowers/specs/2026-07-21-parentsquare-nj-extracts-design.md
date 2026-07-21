# ParentSquare (NJ) Outbound Extracts — Design

- **Issue:** [#4480](https://github.com/TEAMSchools/teamster/issues/4480)
- **Asana:** Summer 2027 : SIS Portfolio, task 1216377560708697 (Rebuild Student
  Contacts)
- **Status:** design
- **Author:** Data Team

## Context

ParentSquare is the family-communications platform succeeding Finalsite for
student contacts (the "Rebuild Student Contacts" workstream). It needs a
recurring roster feed from the warehouse — students, guardians, staff,
enrollments, section rosters, schools — plus attendance so it can drive absence
notifications.

This is a net-new outbound extract set. No ParentSquare code exists in the repo
today. The build reuses the established BigQuery-to-SFTP extract pattern
(`build_bigquery_query_sftp_asset`), the same one behind the Clever, Illuminate,
and PowerSchool `autocomm` feeds.

"NJ" is the three New Jersey regions: Newark, Camden, and Paterson. Miami (Focus
SIS) is out of scope.

## Goals

- One network-wide NJ ParentSquare feed delivering the core roster file set plus
  attendance.
- Cross-file record keys that are PowerSchool-native and mutually consistent, so
  ParentSquare can stitch students, guardians, staff, sections, and schools
  together on its side.
- A build that can start immediately on the parts that do not depend on the two
  open Ops blockers, then reconcile once those land.

## Non-goals

- Terms/calendar file — excluded unless Ops confirms ParentSquare needs it (open
  question 3).
- A dedicated staff/guardian roles file — assumed roles are managed in the
  ParentSquare app (open question 2).
- A reusable cross-tool comms/contacts abstraction layer — YAGNI; there is no
  second consumer.
- Miami / any non-NJ region.

## Approach

Mirror the Clever feed. A single set of `rpt_parentsquare__*` reporting views in
the `kipptaf` (network) dbt project, filtered to the three NJ regions, each
serialized to a file and pushed to a new `parentsquare` SFTP destination by the
generic extract factory. Files are full snapshots on every run; ParentSquare
reconciles adds/changes/removals on ingest, exactly as Clever and Illuminate do.

### Alternatives considered

- **Reusable `int_parentsquare__*` layer feeding multiple comms tools.**
  Rejected — no second consumer exists, so it adds indirection with no payoff.
  If another tool later needs the same shaped data, promote then.
- **Idempotent import/diff pattern (the finalsite-to-focus model).** Rejected —
  that pattern exists because Focus imports are one-shot and must not be
  re-applied. ParentSquare's SFTP roster sync takes full snapshots and dedupes
  on its side, so a diff/import-once layer is unnecessary complexity. Revisit
  only if Ops reports ParentSquare cannot accept full-snapshot re-sends.

## Components

1. **dbt models** — `src/dbt/kipptaf/models/extracts/parentsquare/`, one
   `rpt_parentsquare__<entity>.sql` per file plus a `properties/` YAML carrying
   the contract and tests. These land in the `kipptaf_extracts` schema
   (`extracts/` directory default: view materialization, `contract: enforced`).

1. **Extract config** —
   `src/teamster/code_locations/kipptaf/extracts/config/parentsquare.yaml`, one
   asset block per file. Wired in `kipptaf/extracts/assets.py` with
   `destination_config={"name": "parentsquare"}`, following the
   `clever_extract_assets` list-comprehension pattern.

1. **Destination resource** — `SSH_PARENTSQUARE` (an `SSHResource`) in
   `src/teamster/core/resources.py`, wired as `ssh_parentsquare` into
   `kipptaf/definitions.py`. Host / username / password / port env vars added to
   `dagster-cloud.yaml` in **both** the server and run-pod blocks (per
   `kipptaf/CLAUDE.md`, a secret needs four insertion points). Credentials come
   from Ops blocker 2.

1. **Job + schedule** — `kipptaf__extracts__parentsquare__asset_job` in
   `extracts/jobs.py`, plus a daily `ScheduleDefinition` (~3-4am ET) in
   `extracts/schedules.py`. Shipped paused (`default_status` stopped) until the
   SFTP round-trip is verified.

1. **Exposure** — a dbt exposure in `src/dbt/kipptaf/models/exposures/` per the
   repo rule that every external consumer has one.

## Data flow

Each `rpt_parentsquare__*` model reads existing network models, filters to NJ +
current academic year + active enrollments (the Clever predicate shape), and
projects the ParentSquare column set.

| File                             | Source model(s)                                                                                                      | Cross-file key                                  |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| students                         | `int_extracts__student_enrollments`                                                                                  | `student_id = student_number`                   |
| guardians / contacts             | `int_students__contacts`                                                                                             | linked by `student_number`                      |
| staff                            | PowerSchool teachers/users (`int_powerschool__teachers`, `stg_powerschool__teachers`, `stg_powerschool__users`)      | `staff_id = teachernumber`                      |
| enrollments / section membership | `base_powerschool__course_enrollments` (filter `is_dropped_section`)                                                 | `student_number`, `section_id`, `school_number` |
| section-to-teacher slots         | `stg_powerschool__sectionteacher` to `int_powerschool__teachers` (plus `stg_powerschool__roledef` for slot ordering) | `teachernumber`                                 |
| schools                          | `stg_powerschool__schools`                                                                                           | `school_id = school_number`                     |
| attendance                       | `fct_student_attendance_daily`                                                                                       | `student_number`, `school_number`               |

### ID-consistency principle

Every cross-file key is PowerSchool-native: `student_number`, `school_number`,
`teachernumber`, `sectionid`. The staff file is keyed on `teachernumber` (not
the ADP-derived `employee_number`) precisely so ParentSquare can join teacher to
section to school. `section_id` follows the Clever convention of a
region-prefixed section id
(`concat(regexp_extract(_dbt_source_relation, r'(kipp\w+)_'), sections_id)`) to
stay globally unique across the three regions.

### Caveats carried from upstream

- **`base_powerschool__course_enrollments` double-writes** (#3900 / #3915):
  filter `is_dropped_section` first; add no defensive dedupe. The residual
  fan-out is covered by an existing warn-level uniqueness test upstream.
- **Union-model joins:** `base_powerschool__course_enrollments` is a union model
  — join with the `union_dataset_join_clause` macro (or `_dbt_source_project`
  equality), never on raw `_dbt_source_relation`.
- **Paterson attendance** (#4193): `attendance_value` is unreliable for Paterson
  (upstream PowerSchool conversion-items gap); `membership_value` is clean.
  Paterson is in scope for the roster files; its attendance file may need to be
  membership-only or held until #4193 resolves — see open question 1.

### Provisional file contents

Column-level detail is authoritatively set by the Ops roster spec (blocker A).
The following first-pass column sets are derived from the Clever analog and
ParentSquare's standard SFTP roster format, used to scaffold Phase 0; they will
be reconciled against the Ops spec before delivery.

- **students** — `student_number`, `school_number`, first/middle/last name,
  grade, dob, gender, email, EL/IEP flags, state id.
- **guardians/contacts** — `student_number`, contact name, relationship, contact
  type (primary vs emergency), phone(s), email. Emergency-contact flag preserved
  from `int_students__contacts`.
- **staff** — `teachernumber`, `school_number`, name, email, title.
- **enrollments** — `student_number`, `section_id`, `school_number`.
- **sections** — `section_id`, `school_number`, section/course identifiers, term
  dates, teacher slot(s) keyed on `teachernumber`.
- **schools** — `school_number`, name, grade span, address, principal.
- **attendance** — `student_number`, `school_number`, date, attendance code.

## Sequencing around the blockers

The two Asana subtasks gate the _final_ delivery, not the whole build. Most of
the work is unblocked today.

1. **Phase 0 — now, unblocked.** Build all `rpt_parentsquare__*` models with
   properties/tests, the `parentsquare.yaml` config, the `ssh_parentsquare`
   resource class, the `dagster-cloud.yaml` env-var entries (names/placeholders,
   no secret values committed), the exposure, and the paused job + schedule.
   Validate model SQL and the asset graph in a branch deployment materializing
   against `teamster-test`. Use the provisional column sets above.

1. **Blocker A — Ops roster spec (subtask 1).** Obtain the authoritative
   required columns per file, ParentSquare's expected id conventions, the
   roles-in-app answer, and whether a terms file is needed. Reconcile the Phase
   0 model column names, formats, and filenames against it.

1. **Blocker B — SFTP credentials (subtask 2).** Populate the
   `dagster-cloud.yaml` secret values, finish wiring `ssh_parentsquare`, and
   verify a one-file round-trip to the ParentSquare SFTP before sending the full
   set.

1. **Phase Final.** Un-pause the schedule, confirm ParentSquare ingests the
   files cleanly, and hand off to Ops.

Phase 0 is what writing this spec unblocks: it defines the target precisely
enough that the model/config/resource scaffolding can proceed in parallel with
the Ops conversations.

## Error handling and operational concerns

- **Empty-result guard.** The factory returns early on a zero-row query
  (`transform_data` crashes on empty CSV) — do not remove it. A model that
  legitimately can be empty on a given day is fine; a model that is
  _unexpectedly_ empty should be caught by a dbt test, not the extract.
- **SFTP retry.** `load_sftp` already retries `TimeoutError` / `OSError` /
  `EOFError` / `SSHException` with exponential backoff — no extra handling
  needed.
- **Branch-deploy schema redirect.** Use `query_config.type: schema` (not
  `text`/`file`) so `construct_query` prefixes `zz_dagster_` under a branch
  deployment and the feed reads test data, never prod, during validation.
- **Paused-until-verified.** The schedule ships stopped so an unverified feed
  cannot push to a live ParentSquare SFTP before the round-trip check.
- **PII.** These files carry student and guardian PII (names, contact info,
  dob). Delivery is SFTP-to-vendor only. No PII values go to the issue, PR,
  Asana, or any other external surface; validation output stays local
  (`.claude/scratch/`, terminal). The dbt models must tag PII columns per the
  repo's `config.meta.contains_pii` convention.

## Testing and validation

- **dbt:** contract enforcement plus a uniqueness test on every
  `rpt_parentsquare__*` model (repo requirement for `rpt_` models). Reuse
  Clever-style predicates and validate row counts and key uniqueness against
  prod via the BigQuery MCP.
- **Asset graph:** `dagster definitions validate` (or a targeted module import
  in the codespace) for the extended `kipptaf` extracts wiring.
- **Round-trip:** in a branch deployment, materialize one file end-to-end to a
  test SFTP path first, confirm the file lands and parses, then enable the full
  set.
- **Vendor ingest:** with Ops, confirm ParentSquare ingests each file without
  match/id errors before un-pausing.

## Open questions

1. **Paterson attendance.** In scope for roster files; is its attendance feed
   membership-only, deferred until #4193, or accepted as-is?
1. **Roles in app.** Confirm staff/guardian roles are set within ParentSquare,
   so no role column is fed (answers the task's "Can roles be set on app?").
1. **Terms/calendar.** Does ParentSquare need a terms/calendar file?
1. **ID conventions.** What student / staff / guardian id formats does
   ParentSquare expect for record matching? (Assumed PowerSchool-native.)
1. **Attendance window and cadence.** Full year vs rolling window; daily vs
   intraday delivery.
1. **Delivery format.** Filenames, header row on/off, delimiter, single vs
   per-file remote directories.
1. **Non-teaching staff.** Campus/CMO staff have no `teachernumber`. Does the
   staff feed need them, and what id do they carry if so? (Clever synthesizes
   assignments from the ADP roster + LDAP groups and pulls non-PS
   `int_people__temp_staff` on `employee_id`.)

## References

- Extract factory: `src/teamster/libraries/extracts/assets.py` and its
  `CLAUDE.md`.
- Clever analog: `src/dbt/kipptaf/models/extracts/clever/rpt_clever__*.sql`;
  config `src/teamster/code_locations/kipptaf/extracts/config/clever.yaml`.
- Destination-resource pattern: `SSH_*` resources in
  `src/teamster/core/resources.py`.
- Contacts source: `int_students__contacts`, `int_finalsite__student_contacts`
  (see `kipptaf/CLAUDE.md` finalsite notes).
- Upstream caveats: #3900 / #3915 (course-enrollment double-writes), #4193
  (Paterson attendance).
