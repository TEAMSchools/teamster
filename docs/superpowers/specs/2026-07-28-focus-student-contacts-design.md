# Miami student contacts: replace frozen PowerSchool with Focus

- **Issue**: [#4585](https://github.com/TEAMSchools/teamster/issues/4585)
- **Asana**:
  [Student Contacts FL - Replace with Focus](https://app.asana.com/1/913513768672/project/1215209393570629/task/1216356414391207)
- **Date**: 2026-07-28
- **Status**: Approved design; Phase 1 ready to plan

## Problem

The Miami branch of `int_students__contacts` (kipptaf) still reads the frozen
`kippmiami_powerschool` BigQuery dataset via `int_powerschool__contacts` and
`int_powerschool__person_contacts` — a snapshot from before Miami's SIS
migration to Focus. Miami contact data in network reporting
(`dim_student_contact_persons`, `bridge_student_contacts`,
`rpt_gsheets__student_contact_info`) is stale and degrading.

This is the Miami counterpart of the NJ Finalsite contacts cutover
([#4346](https://github.com/TEAMSchools/teamster/issues/4346),
[#4400](https://github.com/TEAMSchools/teamster/issues/4400)).

## Decisions already made

- **Focus is the system of record** for Miami contacts going forward. The
  Finalsite→Focus contacts import-once SFTP feed (`rpt_focus__contacts`) keeps
  seeding new enrollees; registrars maintain contacts natively in Focus. No
  circular-flow concern.
- **Two-phase delivery.** Focus currently holds almost no contact data (1
  `students_join_people` link vs 3,874 students — the Finalsite contacts import
  has not landed in Focus). Phase 1 builds the models now, validated
  structurally; Phase 2 flips `int_students__contacts` and retires the
  PowerSchool contacts chain once Focus contacts are populated.
- **Slotting stays out of the intermediate.** `int_focus__student_contacts`
  emits every student↔contact link, unslotted and uncapped. The `contact_slot`
  vocabulary (`contact_1`, `emergency_N`) is applied at the kipptaf reporting
  layer in Phase 2, where downstream compatibility defines it.
- **Architecture**: mirror the NJ pattern — SIS-specific logic lives in the
  `focus` source package (built by `kippmiami`), consumed by kipptaf via
  `source()` + thin union wrapper. (Alternatives considered and rejected:
  building the logic in kipptaf over the raw dlt dataset — breaks layering,
  duplicates package typing/soft-delete handling; building in the `kippmiami`
  project — no `int_focus__*` precedent lives there.)

## Source data map (verified 2026-07-28)

Dataset: `dagster_kippmiami_dlt_focus` (dlt-loaded nightly; loads current as of
this morning).

| Target field                                    | Focus source                                                                                                                                                             |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| student↔contact link, relation, ordering, flags | `students_join_people`: `student_relation`, `sort_order`, `custody`/`emergency`/`pick_up` (`'Y'`/null), `address_id`, `reunification`                                    |
| contact name, email                             | `people` (`first_name`, `middle_name`, `last_name`, `email`) — **no staging model exists yet**                                                                           |
| phones by type                                  | `people_join_contacts`: `title` + `value` rows with `detail_priority`, `blocked`, `unlisted`, `sms` (only 3 rows today, title "Cell Phone")                              |
| home address / household membership             | `address` via `students_join_people.address_id`; student's own addresses via `students_join_address`                                                                     |
| student identity                                | `students.student_id` (PK) = `'8400' + Finalsite-minted id`; equals `custom_53` (`local_student_id`); legacy ids embed the PS `student_number` (`8400300007` ↔ `300007`) |

Facts that shape the design:

- The Finalsite→Focus import feed (`kipptaf rpt_focus__contacts`) leaves
  `custody`/`emergency`/`pickup`/`resides_with_stud` **null** and imports only
  relationship-typed contacts (parent/guardian/grandparent/stepparent/relative/
  aunt-uncle), `sort_order` = primary-first then alphabetical. Emergency flags
  will only exist once registrars maintain them in Focus — the read-back model
  must treat the flags as nullable booleans, not assume population.
- Focus soft-delete convention: `deleted` is null for live rows, `1` for deleted
  (never `0`) — staging filters `where deleted is null`.
- For new (post-PowerSchool) Miami students, `stg_people__student_logins`
  already uses the **prefixed** Focus id cast to int64 as `student_number` — the
  Miami student-number space is in transition (see Phase 2 open question).

## Phase 1 — build the Focus contacts models (PR 1)

### `stg_focus__people` (new; `src/dbt/focus/models/staging/`)

Contract-enforced staging over the `people` table, per package conventions:
`where deleted is null`, drop dlt bookkeeping and audit-quad columns, PK
`person_id` with `unique` + `not_null` at `severity: error`. Project the name
fields, `email`, `birthdate`, `primary_language`, `created_at`/`updated_at`.
Properties yml with full column descriptions and `data_type`s.

### `int_focus__student_contacts` (new; `src/dbt/focus/models/intermediate/`)

- **Grain**: one row per live `students_join_people` link (`student_id` ×
  `person_id`; enforce with `dbt_utils.unique_combination_of_columns`).
- **No slotting, no caps** — every contact row flows through with its
  `sort_order` and flags; consumers restrict.
- Columns (aligned to the `int_finalsite__student_contacts` vocabulary where the
  concept matches):
  - identity: `student_id`, `local_student_id`, `person_id`
  - person: `contact_name` (first + last), `contact_first_name`,
    `contact_last_name`, `relationship` (from `student_relation`), `email`
  - ordering: `sort_order`
  - flags: `is_custodial`, `is_emergency`, `is_pickup`, `is_reunification`
    (normalized from `'Y'`/null, **null-preserving** — `null` means
    "unmaintained in Focus", which is real signal while the import-seeded rows
    carry no flags; the Phase 2 slotting treats only `true` as
    emergency-qualifying)
  - phones: `phone_mobile` / `phone_home` / `phone_work` / `phone_daytime`
    pivoted from `people_join_contacts.title`, `phone_primary` = lowest
    `detail_priority` phone; all through `clean_phone`
  - address: `home_address` assembled from `address` via the link's
    `address_id`; `is_household_member` = link `address_id` matches one of the
    student's own `students_join_address` rows
- The `people_join_contacts.title` domain is nearly empty today ("Cell Phone"
  only). Implement the pivot against Focus's documented contact-type list (see
  `docs/superpowers/specs/references/focus-db-erd.md` and the import feed's
  `contactN_type` values), and leave unmatched titles surfaced via a warn-level
  accepted-values-style test so new types are caught, not dropped silently.

### kipptaf plumbing (same PR, inert)

- Add `int_focus__student_contacts` to
  `src/dbt/kipptaf/models/focus/sources-kippmiami.yml` (existing focus source;
  dev/staging schema branch already in place).
- Add a kipptaf thin union wrapper `int_focus__student_contacts`
  (single-relation `dbt_utils.union_relations` + `_dbt_source_project`),
  following `int_focus__school_year_first_day`.
- **No consumer changes** — `int_students__contacts` untouched in this PR.

### Phase 1 validation

- `uv run dbt build --select stg_focus__people+ --project-dir src/dbt/kippmiami --defer --state <prod manifest>`
  (package models build via the consuming district).
- Contract enforcement + uniqueness tests pass; models legitimately hold ~1 row
  until the Focus import lands.
- `trunk check --force` on changed SQL/YAML from inside the worktree.
- dbt Cloud CI note: a district/package-only PR gets a no-op kipptaf run; the
  kipptaf source + wrapper addition is exercised only if `state:modified+`
  reaches it — verify the wrapper builds locally regardless.

## Phase 2 — the swap (PR 2; gated on Focus contacts data landing)

Gate: Focus `students_join_people` link count reaches the same order of
magnitude as enrolled students (~4k), i.e. the Finalsite contacts import has run
(Ops-owned; timing unknown).

- In `int_students__contacts` (kipptaf): replace the `ps_*` CTE chain (base,
  slotting, person-contacts enrichment, primary-phone ranking, frozen-students
  join) with a `focus` branch reading the kipptaf wrapper:
  - slot here: `contact_1` = `sort_order` 1 per student; `emergency_N` =
    emergency-flagged links ranked by `sort_order`; cap at the reporting layer
    if needed (downstream currently reads `contact_1`/`contact_2` as guardians
    and `emergency_*` as others; the Miami PS branch never emitted `contact_2`).
  - map to the union contract: `personid` = Focus `person_id` as string,
    `finalsite_contact_id` = null, phones/email/address/flags direct.
  - join to the Miami enrollment spine for `student_number` — resolve which form
    (legacy 6-digit vs prefixed 10-digit Focus id) the spine uses at flip time.
- Retire the kipptaf PowerSchool contacts chain: drop
  `int_powerschool__contacts` (SQL + properties) and remove the
  `int_powerschool__person_contacts` / `int_powerschool__contacts` table entries
  from the powerschool `sources-kippmiami.yml`. The frozen
  `kippmiami_powerschool` dataset itself stays (still feeds
  `int_fldoe__all_assessments` and other consumers).
- Verify downstream compiles and grain tests: `dim_student_contact_persons`,
  `bridge_student_contacts`, `bridge_survey_expectations`,
  `fct_survey_submissions`, `rpt_gsheets__student_contact_info`.
- `rpt_deanslist__family_contacts` stays NJ-only; extending it to Miami is out
  of scope (separate task if Ops requests).

### Phase 2 validation

- Sanity diffs at flip (frozen-vs-live means exact matches are not expected):
  per-school `contact_1` coverage vs the outgoing PS branch; non-null
  phone/email rates; `emergency_*` volume.
- Grain test on `int_students__contacts` (existing) proves no double-counting
  across branches.

## Open questions (carried to Phase 2)

1. Exact `people_join_contacts.title` value domain once real data lands.
1. Which `student_number` form the Miami enrollment spine uses at flip time
   (legacy 6-digit vs `8400`-prefixed) — depends on the parallel SIS-portfolio
   enrollment work.
1. Timing of the Focus contacts import (Ops-owned) — sets the Phase 2 date.

## Out of scope

- Any Dagster/ingestion changes (the `people*` tables are already dlt-loaded).
- DeansList family-contacts extract for Miami.
- Changes to the Finalsite→Focus import feeds (`rpt_focus__*`).
- NJ regions (already Finalsite-sourced).
