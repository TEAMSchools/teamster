# Finalsite → Focus enrollment integration (KIPP Miami) — design

- **Issue:** [#4073](https://github.com/TEAMSchools/teamster/issues/4073)
- **Status:** Design / brainstorming output (no implementation yet)
- **Scope:** KIPP Miami only (`kippmiami` code location)
- **Related:** inbound Focus-load spec
  `2026-04-03-focus-sis-integration-design.md` (distinct pipeline — that loads
  Focus → warehouse; this pushes Finalsite → Focus)
- **API reference:** `references/focus-api-spec.md` (+ `.json`)

## Goal

Finalsite Enrollment is the **system of record** for student enrollment,
transfers out, re-enrollment, and contacts at KIPP Miami. This integration keeps
Focus (the SIS) continuously in sync with Finalsite — creating new enrollees
**and updating existing Focus students after creation** across the full
lifecycle — so staff never re-enter enrollment data in Focus.

## Direction & scope

- **One-directional (Finalsite → Focus) but ongoing.** Finalsite is SoR; Focus
  is the continuously-updated downstream. This is **not** a two-way sync — the
  only reverse flow is writing the resolved `student_id`/`uuid` back to
  Finalsite. But it is an ongoing **upsert + lifecycle** sync, not a one-time
  create (see _Sync operations_).
- **Miami only.** Focus is Miami's SIS; Newark/Camden/Paterson use PowerSchool.
  Build in `kippmiami`, alongside the existing Focus DLT and Finalsite assets.

## Architecture — warehouse-first with two pluggable forks

Everything from staging through "Focus-shaped output" is shared and built
regardless of how the two open forks resolve. The forks live only at the edges.

```text
Finalsite  [FORK 1: REST API  OR  new SFTP export]
  -> GCS (Avro) -> BigQuery raw [kippmiami]
  -> dbt staging            (normalize the chosen source to one common shape)
  -> dbt eligibility filter (accepted/enrolled, target school year)
  -> dbt identity resolution  <-> persisted crosswalk
  -> dbt Focus-shaped output models  (API shape and/or 5 SFTP-template shapes)
  -> [FORK 2: Focus SFTP templates  OR  Focus REST API]
  -> [optional] write resolved student_id + Focus uuid back to Finalsite
  -> reconciliation: Finalsite eligible roster vs Focus students
```

### Fork 1 — Finalsite source (decide when the export file lands)

Not sequential ("API now, SFTP later" was a mischaracterization). The source
will be **either** the Finalsite REST API **or** the promised all-in-one SFTP
export. Decide which is better once the export exists and can be compared on
contents, completeness, freshness, and effort. The dbt **staging layer
normalizes whichever source into one shape**, so the rest of the pipeline is
source-independent. The existing Finalsite warehouse assets serve a different
purpose and are not reused as-is.

### Fork 2 — Focus transport (decide after vendor confirmation)

**Either** is viable; the choice is **neutral on identity grounds** (we supply
the student number on both paths — see Identity). Decide on the other factors
below.

|                   | Focus SFTP templates                                                                                         | Focus REST API                                                                                                                                    |
| ----------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Shape             | 5 coordinated CSVs (Demographics, Student_Enrollment, Address, Contacts, Linked_Students) keyed on `STDT_ID` | `POST /student` (student + demographics + 2 guardians + address + accepting grade/school/program/year), `PUT /student/:uuid`, `POST /multi` batch |
| Auth/setup        | SFTP creds; files to `/uploaded-assets/export/`, static filenames, UTF-8, fixed column order                 | OAuth2 `client_credentials`; Focus admin provisions a Third Party System (Focus dialect, write scope, Client ID/Secret)                           |
| Enrollment record | `STUDENT_ENROLLMENT` template creates it                                                                     | `enrollments`/`school_enrollments` are **GET-only** — unclear if `POST /student` accepting\_\* fields create the enrollment (vendor-confirm)      |
| Guardians         | Many (Contacts + SORT_ORDER)                                                                                 | Exactly 2                                                                                                                                         |
| Error feedback    | After Focus processes batch; mismatches land in manual "Match Students" queue                                | Per-record, synchronous                                                                                                                           |
| Repo precedent    | Reuses `build_bigquery_query_sftp_asset`                                                                     | Net-new outbound OAuth2 POST resource                                                                                                             |

Possible hybrid: API for the student record + SFTP `STUDENT_ENROLLMENT` for the
enrollment, if the API can't create enrollments.

## Sync operations (lifecycle)

Finalsite is SoR for the full student lifecycle. The integration applies each of
these to Focus on an ongoing basis — not just at initial enrollment:

| Operation               | Finalsite trigger                 | Focus effect                                                 | Transport notes                                                                                        |
| ----------------------- | --------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| **Create**              | New accepted/enrolled contact     | New student + demographics + address + contacts + enrollment | SFTP full template set, or API `POST /student` (+ enrollment — see gap)                                |
| **Update after create** | Any change to an existing student | Update the matched Focus student                             | SFTP refresh (re-send current state) or API `PUT /student/:uuid` (needs `uuid` from crosswalk)         |
| **Transfer out**        | Withdrawal / drop in Finalsite    | End-date / drop the enrollment                               | SFTP `STUDENT_ENROLLMENT` `END_DATE`+`DROP_CODE`; **no API enrollment-write** (`enrollments` GET-only) |
| **Re-enrollment**       | Returning student for a new year  | New enrollment row for the existing student                  | SFTP `STUDENT_ENROLLMENT` (per-year file); API path unconfirmed                                        |
| **Contacts**            | Guardian / relationship changes   | Upsert contacts + sibling links                              | SFTP `Contacts`/`Linked_Students` (many) or API `guardian_1`/`guardian_2` (max 2)                      |

Two consequences:

- **Updates require resolving the Focus `uuid`/`student_id` for every record**,
  not just new ones — the persisted crosswalk is load-bearing for the entire
  lifecycle, not a one-time convenience.
- **The enrollment-write gap matters more than for create-only.** Transfers-out
  and re-enrollment are enrollment-record changes, and the API exposes no
  enrollment write (`enrollments`/`school_enrollments` are GET-only). So either
  the SFTP `STUDENT_ENROLLMENT` template is required for those operations (a
  hybrid, even if the API is used for student/contact upserts) or the vendor
  confirms an API path. The SFTP full-refresh model handles the whole lifecycle
  in one mechanism; the API likely cannot alone.

## Identity (the crux) — resolved model

KIPP owns the canonical student number. Confirmed against live Focus data (3,453
migrated students):

| Field                                         | Shape    | Origin                                     | Role                                                                  |
| --------------------------------------------- | -------- | ------------------------------------------ | --------------------------------------------------------------------- |
| `student_id` (= `custom_53` / `local_id`)     | 10-digit | **KIPP-supplied** at migration (`STDT_ID`) | **Canonical KIPP student number (current scheme)**                    |
| `custom_l1482` (`powerschool_student_number`) | 6-digit  | KIPP-supplied                              | **Legacy** PowerSchool number, preserved for the migrated cohort only |
| `uuid`                                        | uuid     | Focus-generated                            | Internal record / API key                                             |

Implications:

- The number is **ours**: we seeded `student_id` to our 10-digit scheme; the
  `STDT_ID` import key landed in `custom_53` and equals `student_id` for every
  row. For the migrated cohort, Focus generated only `uuid` (we supplied
  `student_id`); whether Focus mints `student_id` for _new_ records is open
  decision #1.
- **Crosswalk anchored on `student_id`** (current scheme). Match Finalsite
  enrollees to an existing `student_id` where the student already exists; assign
  a new number for genuinely-new enrollees. Persist the crosswalk
  (`finalsite_contact_id ↔ student_id ↔ focus_uuid ↔ match_state`) so IDs are
  stable across runs and can be written back to Finalsite.
- **Legacy `custom_l1482`** is a historical bridge for reconciling the existing
  cohort to PowerSchool-era / Finalsite history. New students never have one.
- Focus's manual **"Match Students"** tool is the fallback our resolution exists
  to minimize — the cleaner we resolve identity before sending, the fewer
  duplicates and less manual pairing in Focus.

## Components

1. **Ingestion (source-agnostic)** — land the chosen Finalsite source into
   BigQuery (Avro on GCS, existing patterns).
2. **Lifecycle scope & state mapping** — a documented, configurable mapping from
   Finalsite status / enrollment_type / year to the in-scope set **and the Focus
   operation** (create / update / transfer-out / re-enroll). More than a "who
   gets sent" gate — it classifies each record's lifecycle action.
3. **Identity resolution + persisted crosswalk** — anchored on `student_id`,
   legacy bridge via `custom_l1482`. Resolves the Focus `uuid`/`student_id` for
   **every** in-scope record (updates and transfers, not just creates).
4. **Focus-shaped output models** — API wide-row shape and/or the 5
   SFTP-template shapes; shared upstream makes adding the second cheap.
5. **Transport seam** — applies create / update / drop per record. SFTP via
   `build_bigquery_query_sftp_asset` (static filenames, full refresh of in-scope
   students) **or** a new `FocusResource` (OAuth2 client_credentials, token
   cache/refresh, 429 handling) posting `POST`/`PUT` per student or via
   `/multi`, capturing returned `uuid` and per-record errors.
6. **Change detection & cadence** — full refresh of the in-scope set each run
   (simplest; matches SFTP's keyed-replace model) **or** incremental via
   Finalsite `since` / `since_includes_expanded`. Ongoing schedule (e.g. daily,
   more frequent in peak enrollment season).
7. **Write-back** — push resolved identifiers to Finalsite (Update-Fields API)
   so later runs match trivially: always the Focus `uuid`; plus `student_id` if
   Focus/we minted it (under option 1a Finalsite already holds it). Only reverse
   flow.
8. **Validation / observability** — Avro schema checks on ingest; crosswalk
   tests (no dupes, every in-scope student resolves); reconciliation model
   (Finalsite in-scope roster vs Focus students via existing DLT data) that also
   catches missed updates/drops, not just missed creates.

## PII handling

Student/guardian PII stays in the warehouse and local artifacts. Any external
surface (PR, issue, Asana, logs) uses redacted labels or column-name references
only. Counts/aggregates are fine; identifiers are not.

## Open decisions & gates (do not block writing/implementation planning)

1. **★ Go-forward number minting.** Who assigns the 10-digit `student_id` for a
   brand-new enrollee. Per Finalsite's
   [ID Generation & Sync to Third-Party Systems](https://schooladmin.zendesk.com/hc/en-us/articles/6219105734925-ID-Generation-Sync-to-Third-Party-Systems)
   doc, Finalsite supports rule-based ID generation (incrementing numbers or
   composite values like `LAST + FIRST + DOB`, with formatting such as leading
   zeros), and its native API integrations use a "the SIS generates an ID and
   sends it back to Finalsite" round-trip. Options:
   - **(a) Finalsite mints it** via rule-based ID generation (the API exposes
     this read-only on the `Field` object: `ctype: IdField`,
     `id_field_autogenerate`, `id_field_template`, `id_field_counter`;
     per-contact value in `id_attributes`). We read it and push to Focus.
     Cleanest fit since Finalsite is SoR — no minting logic in our pipeline.
     Confirm with Finalsite: counter scope/uniqueness, template tokens, whether
     it matches the existing 10-digit format, and that ID-field setup is a
     UI/admin task.
   - **(b) Focus mints, we return it to Finalsite** — mirrors Finalsite's native
     pattern (SIS generates the id, sends it back). But that round-trip is
     pre-built only for Blackbaud/Veracross, **not Focus**, and it's unknown
     whether Focus auto-increments our scheme — so we'd implement the
     capture-and-write-back ourselves.
   - **(c) We mint** the next number in the pipeline (needs an allocation
     authority / sequence).

   Identity-resolution absorbs whichever via one config flag. Formal ownership
   sign-off: Miami ops / central data.

2. **Fork 1** — Finalsite source (API vs new SFTP export); decide when the
   export lands.
3. **Fork 2** — Focus transport (SFTP vs API); decide after vendor confirmation.
4. **API vendor-confirm items** — create-vs-update match key field on re-POST;
   and the **enrollment-write gap**: whether the API can create/end enrollments
   (transfers-out, re-enrollment) or the SFTP `STUDENT_ENROLLMENT` template is
   required for those operations (likely hybrid). `enrollments` are GET-only.
5. **Change detection** — full refresh vs incremental (`since`); and run cadence
   (ongoing, with a likely peak-season frequency bump).
6. **Schema detail (build-time)** — whether `student_id` is Focus's true PK
   accepting supplied values, or `uuid` is the PK and `student_id` a number
   column. Doesn't change the design.
7. **Prereqs** — Focus admin provisions a Third Party System integration (Focus
   dialect, write scope, Client ID/Secret) for the API path; required Focus
   codes (grades, enrollment codes, calendars) exist; guardian cardinality (API
   = 2, SFTP = many).

## Out of scope

Two-way **data** sync (Focus → Finalsite beyond writing the resolved id back);
non-Miami regions; migrating the existing cohort (already done); the inbound
Focus → warehouse load (separate spec). Note: ongoing updates, transfers-out,
re-enrollment, and contacts are explicitly **in** scope (Finalsite → Focus) —
see _Sync operations_.
