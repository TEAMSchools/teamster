# Finalsite → Focus enrollment integration (KIPP Miami) — design

- **Issue:** [#4073](https://github.com/TEAMSchools/teamster/issues/4073)
- **Status:** Design / brainstorming output (no implementation yet); updated
  2026-06-09 — Fork 1 resolved to the **REST API**, live-validated against
  Miami; `START_DATE` sourced from `stg_finalsite__status_report` (see _Fork
  1_).
- **Scope:** KIPP Miami only (`kippmiami` code location)
- **Related:** inbound Focus-load spec
  `2026-04-03-focus-sis-integration-design.md` (distinct pipeline — that loads
  Focus → warehouse; this pushes Finalsite → Focus)
- **API reference:** `references/focus-api-spec.md` (+ `.json`)
- **Source sample:** Finalsite Swiss Army Export "Focus Student Export" SFTP CSV
  (`kippmiami_SwissArmyExport_Focus_Student_Export…_SFTP_…`, 2026-06-02). PII —
  held in Drive, **not committed** to the repo. Schema documented in _Fork 1_.

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

### Fork 1 — Finalsite source: RESOLVED → REST API (live-validated 2026-06-09)

**Decision: source from the Finalsite REST API.** Validated live against Miami
(`kippmiami.fsenrollment.com`): a single paginated call —
`GET /contacts?school_year_id={current}&count=25&includes=contacts.relationships.contact`
(paginate via `meta.next_cursor`) — reproduces **every column of the SFTP "Focus
Student Export."** The only field not directly present is `Enrolled Date`
(sourced from the Status Report — see below); the gendered `mother`/`father`
relationship label is **derived** from `relationships[].rel_type` + the
guardian's `gender` (validated: `parent`+`F`→mother, `parent`+`M`→father, etc.,
falling back to the bare `rel_type` when gender is unset — reproducing the
export exactly). Per student it returns base demographics + `grade` +
`households` (address) + `custom_attributes` (Miami names confirmed: `race_ms`,
`assigned_school_ss`, `med_doctor_txt`/`med_hospital_txt`/…, `mdcps_id_txt`,
`sped_received_yn`, `latino_hispanic_yn`) + `id_attributes` + **fully-expanded
guardian contacts** (name/email/phone) via the `contacts.relationships.contact`
include. The dormant `build_finalsite_asset` + `FinalsiteResource` (JWT) already
implement this auth + pagination, so wiring Miami contacts ingestion is mostly
config. The dbt **staging layer normalizes the source into one shape**, so
downstream is source-independent.

**`Enrolled Date` (= `START_DATE`) is not in the API** — confirmed not in
`contact_statuses` (catalog only), not reachable by any expansion (unknown
`includes` tokens are silently ignored), and absent from the full payload (0
minute-precision matches across 20 students). It is a workflow status-change
timestamp the API does not expose. **Resolution (decided):** join the
already-ingested **`stg_finalsite__status_report.enrolled_date`** on
`finalsite_enrollment_id` (= the API `contact.id`; UUID, 2529/2529). That
Status-Report SFTP feed also carries the full status-transition timeline
(`accepted_date`, `enrollment_in_progress_date`, `assigned_school_date`,
`enrolled_date`, `not_enrolling_date`, `mid_year_withdrawal_date`,
`summer_withdraw_date`, …) — supplying both the **eligibility predicate** and
the **transfer-out `END_DATE`**. So: API for the contact + a keyed join to the
existing Status Report for workflow dates. The new "Focus Student Export" file
is **not needed** as a source.

The SFTP "Focus Student Export" sample documented below remains the **validation
baseline** the API was checked against.

**The SFTP export now exists** (sample dated 2026-06-02), so the comparison has
real data on one side. It is a Finalsite "Swiss Army Export" configured as a
"Focus Student Export," delivered via SFTP: **one flat, denormalized row per
student**, with the address, medical fields, and up to **four** guardians
embedded inline. This is the _source_ shape — distinct from Focus's five
_import_ templates in Fork 2; do not conflate them.

Documented columns (sample):

| Group        | Columns                                                                                                                                    |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Identity     | `Finalsite ID`; SIS-ID slots `PowerSchool DCID`, `PowerSchool Student Number` (see gate)                                                   |
| Student      | First / Middle / Last Name, `Grade`, `Gender`, `Birth Date`, `Latino/Hispanic` (bool), `Race - Multi-Racial` (pipe-delimited multi-select) |
| Address      | `Household 1 Address / City / State / Zip` (single household only)                                                                         |
| Medical      | Student Doctor Name / Phone, `Media Release`, Preference of Hospital, Hospital/Doctor Phone (see gate)                                     |
| Guardians ×4 | per parent: `Finalsite ID`, `PowerSchool Contact ID`, Title, First / Last Name, Relationship, Primary Phone Type / Number, Email           |

Findings that reshape the design:

1. **No enrollment data.** The export carries no enrollment status, school,
   entry date, school year, or withdrawal/drop code — only `Grade`. As
   configured it **cannot drive the eligibility predicate or the lifecycle ops**
   (transfer-out, re-enroll); it only feeds demographics / address / contacts.
   See the _enrollment-data gate_.
2. **SIS-ID slots are PowerSchool-named on a Focus region** — mostly empty, a
   few guardian rows carry a populated contact ID. See the _SIS-ID column gate_.
3. **Up to four guardians** — the source over-supplies relative to the Focus API
   (max 2). With the all-guardians decision (below), this tilts Fork 2 to SFTP.
4. **Medical fields present** — see the _medical-destination gate_.
5. **Single household** — no second address modeled.

**Empirical profile** (sample export, n=167 students, 56 columns, 2026-06-02 —
aggregates only):

- **No enrollment fields, confirmed** — 0 of 56 columns carry status / school /
  entry date / year / program; the only date column is `Birth Date`. Validates
  the _enrollment-data gate_.
- **Identity slots near-empty** — `PowerSchool DCID` / `Student Number`
  populated in ~1.2% of rows; a per-guardian `PowerSchool Contact ID` is present
  on **19.6%** of guardians (returning families partially pre-keyed — bears on
  the _SIS-ID column gate_ and the crosswalk).
- **Guardian distribution** (supports all-guardians → SFTP Contacts): 1 → 51, 2
  → 87, **3 → 23, 4 → 3**; **26 students (15.6%) have ≥3** — the Focus API's
  2-cap would drop guardians for ~1 in 6.
- **Sibling-inference yield** (for `Linked_Students` via shared parent ID): **64
  students (38.3%)** link to ≥1 sibling; 50 distinct pairs.
- **`Race - Multi-Racial` is pipe-delimited multi-select** (8 rows carry
  multiple values) → maps to Focus `RACE_*` Y/N booleans, not just
  `SINGLE_ETHNIC`.
- **`Relationship` is coarse** — generic `parent` dominates (172/306);
  `RESIDES_WITH_STUD` has no source (default required).
- **Data quality:** 3 students (1.8%) have no guardian and no address —
  quarantine rather than push.

**Superseded (2026-06-09).** The earlier "enrich the single SFTP export"
preference is dropped: Fork 1 resolved to the **API** (above), with
`enrolled_date` and lifecycle dates joined from `stg_finalsite__status_report`.
The enrollment-data gate is thereby closed (see _Open decisions_).

### Fork 2 — Focus transport (decide after vendor confirmation)

Both are **neutral on identity grounds** (we supply the student number on either
path — see Identity). For **contacts**, the choice is already made — SFTP, per
the all-guardians decision below (API caps at 2). For the **student/enrollment**
records either remains viable; decide on the factors below.

|                   | Focus SFTP templates                                                                                         | Focus REST API                                                                                                                                    |
| ----------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Shape             | 5 coordinated CSVs (Demographics, Student_Enrollment, Address, Contacts, Linked_Students) keyed on `STDT_ID` | `POST /student` (student + demographics + 2 guardians + address + accepting grade/school/program/year), `PUT /student/:uuid`, `POST /multi` batch |
| Auth/setup        | SFTP creds; files to `/uploaded-assets/export/`, static filenames, UTF-8, fixed column order                 | OAuth2 `client_credentials`; Focus admin provisions a Third Party System (Focus dialect, write scope, Client ID/Secret)                           |
| Enrollment record | `STUDENT_ENROLLMENT` template creates it                                                                     | `enrollments`/`school_enrollments` are **GET-only** — unclear if `POST /student` accepting\_\* fields create the enrollment (vendor-confirm)      |
| Guardians         | Many (Contacts + SORT_ORDER)                                                                                 | Exactly 2                                                                                                                                         |
| Error feedback    | After Focus processes batch; mismatches land in manual "Match Students" queue                                | Per-record, synchronous                                                                                                                           |
| Repo precedent    | Reuses `build_bigquery_query_sftp_asset`                                                                     | Net-new outbound OAuth2 POST resource                                                                                                             |

**Decision (2026-06-02): preserve all guardians.** Miami wants every guardian
the source supplies (the export carries up to four). The Focus API caps at
`guardian_1`/`guardian_2`, so an **API-only path would silently drop guardians**
— it is ruled out for contacts. The SFTP `Contacts` template (+ `SORT_ORDER`)
handles many, so Fork 2 tilts to SFTP; an API path would have to be paired with
SFTP for the `Contacts` file. This does not by itself resolve Fork 2 for the
student/enrollment records — only the contacts portion.

Possible hybrid: API for the student record + SFTP `STUDENT_ENROLLMENT` for the
enrollment, if the API can't create enrollments.

## Source × transport coverage matrix

How completely each **Finalsite source** (SFTP export vs REST API) can populate
each **Focus target** (the 5 SFTP import templates vs the `POST /student` API).
Authoritative field lists: Finalsite API = `references/finalsite-api-spec.yml`;
Focus API = `references/focus-api-spec.json`; Focus SFTP = the FL K-12 import
workbook; Finalsite SFTP = the landed export (_Fork 1_).

**Legend:** ✓ direct field in the source · ◐ obtainable by pipeline derivation,
config, or a Finalsite custom/track field (not a base column) · ✗ no source.

**Caveats that apply to every cell:**

- `STUDENT_ID` / the Focus key is **pipeline-resolved** (identity/minting gate)
  on all paths — counted ◐, never ✓-from-source.
- The Focus **API marks no field required** (its route registry carries no
  `required` flags). "Required" there = the functional minimum to create + place
  a student: a match key, name, `accepting_school`, `accepting_grade`,
  `school_year`.
- **`START_DATE`/entry date exists in no source** — neither the export nor the
  API `Contact` carries an enrollment start date; it must be derived (first
  instructional day of `school_year`, or the API `contract_submit_date` proxy).
- **Which Focus `SCHOOL` a student enrolls in is in no base source** — derivable
  (region/grade → school) or a Finalsite custom field.
- **Race/ethnicity/language/school live in the API as custom fields — confirmed
  populated** (Newark live profile: `race_ms`, `preferred_language_txt`,
  `kipp_school_*`/`assigned_school_ss`). The base `Contact` exposes gender +
  birth_date; the rest are `custom_attributes`/`track_attributes`. So both
  sources carry race — the API is in fact the broader source. Miami's exact
  custom-field names are per-tenant (confirm when Miami creds land).

### Headline — can we complete the target?

|                             | → Focus SFTP templates                                                        | → Focus API (`POST /student`)                                                                      |
| --------------------------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| **Finalsite SFTP export →** | Demographics ✅ · Address ✅ · Contacts ✅¹ · Linked ✅² · **Enrollment ❌³** | student+demographics ✅ · address ✅ · 2 guardians ⚠️⁴ · **placement ⚠️³**                         |
| **Finalsite API →**         | Demographics ✅⁵ · Address ✅ · Contacts ✅ · Linked ✅ · **Enrollment ⚠️³**  | demographics ✅⁵ · address ✅ · 2 guardians ⚠️⁴ · placement ⚠️³ + **status-driven eligibility ✅** |

¹ `RESIDES_WITH_STUD` not in source → default. ² via shared-parent inference. ³
`SCHOOL` + `START_DATE` not in source (derive); Focus enrollment-code setup
required; **the API cannot write the `enrollments` table at all** — placement
only via `accepting_*`. ⁴ Focus API caps guardians at 2 → violates the
all-guardians decision (data loss). ⁵ race/ethnicity/language/school are API
custom fields, confirmed populated in Newark (per-tenant names — confirm Miami).

### Target A — Focus SFTP templates: required-field coverage

| Focus file (req)       | from Finalsite SFTP                                                              | from Finalsite API                                                       |
| ---------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Demographics (3)       | 3/3 ✓✓◐                                                                          | 3/3 ✓✓◐                                                                  |
| Student_Enrollment (5) | 3/5 — `GRADE_ID`✓ `STUDENT_ID`◐ `SYEAR`◐(config); **`SCHOOL_ID`◐ `START_DATE`✗** | 3/5 — `GRADE_ID`✓ `SYEAR`✓ `STUDENT_ID`◐; **`SCHOOL_ID`◐ `START_DATE`✗** |
| Addresses (1)          | 1/1 ◐                                                                            | 1/1 ◐                                                                    |
| Contacts (5)           | 4/5 — names✓ `SORT_ORDER`◐ `STUDENT_ID`◐; `RESIDES_WITH_STUD`✗(default)          | 4/5 — same                                                               |
| Linked_Students (3)    | 3/3 ◐ (shared-parent inference)                                                  | 3/3 ✓ (`relationships.rel_type`)                                         |

Required count is ~14/17 either way. The API doesn't raise the _count_ but
improves provenance: `SYEAR` and sibling links become direct, and — critically —
`status`/`enrollment_type` (absent from the export entirely) arrive to drive
eligibility and the create / transfer-out / re-enroll classification (both
sources carry race).

### Target B — Focus API `POST /student`: field-group coverage

| Group (47-field flat body)                                                                 | from Finalsite SFTP             | from Finalsite API                               |
| ------------------------------------------------------------------------------------------ | ------------------------------- | ------------------------------------------------ |
| Match key (`student`/`uuid`/`focus_id`)                                                    | ◐ pipeline                      | ◐ pipeline; minted number via `id_attributes`    |
| Names, `birthdate`, `gender`                                                               | ✓                               | ✓                                                |
| Race flags + `ethnicity`                                                                   | ✓ (Race + Latino/Hispanic cols) | ✓ (`race_ms` custom, confirmed Newark)           |
| `accepting_grade`/`current_grade`                                                          | ✓                               | ✓ (`grade.canonical_name`)                       |
| `school_year`                                                                              | ◐ config                        | ✓ (`school_year.start_year`)                     |
| `accepting_school`                                                                         | ◐ derive                        | ✓ (`assigned_school_ss`/`kipp_school_*`, Newark) |
| `accepting_program`, `ese_status`, `preferred_language`, student `email`, `current_school` | ✗ (mostly)                      | ◐/✓ (`email`✓; language/program/ese custom)      |
| `guardian_1/2` (2 only)                                                                    | ✓ but **2 of up to 4**          | ✓ but **2 of up to 4**                           |
| Address (`address`,`city`,`state`,`zipcode`)                                               | ✓; `address2` ✗                 | ✓; `address2` ✓ (`households`)                   |

Both source paths fill the demographic + address + two-guardian core. Neither
cleanly fills placement (`accepting_school`, start date), and **both lose
guardians 3–4** to the API's 2-cap — the reason Fork 2 already tilts to SFTP for
contacts.

### What the matrix decides

1. **No single corner is complete.** Every path needs the identity/minting gate,
   a `START_DATE` derivation, and a `SCHOOL` rule; the Focus API additionally
   can't write the enrollment table and caps guardians at 2.
2. **The export is a thin slice of the API.** Beyond the lifecycle drivers it
   lacks (`status`, `enrollment_type`, `school_year`, sibling `relationships`),
   the live profile shows the API also carries race, school, language, medical,
   IEP, and four emergency contacts (see _Finalsite API live profile_) — so an
   API/hybrid source could fill every gap. The chosen direction stays **enrich
   the single SFTP export**: the profile confirms every field to add already
   exists in Finalsite, so it's a Swiss-Army-Export config change, not a
   data-availability problem. Hybrid/API-source is the fallback. See the
   _enrollment-data gate_.
3. **Focus SFTP target dominates the Focus API target** for this use case: it is
   the only path that creates an actual enrollment record and the only one that
   preserves all guardians. The Focus API is viable for student/demographic
   upserts, never the enrollment.
4. **`status` is the eligibility key** — the active accepted→enrolled set
   (`accepted` / `enrollment_in_progress` / `assigned_school` / `enrolled` /
   `retained`) is "send to Focus", confirmed against the 25-status catalog. The
   current SFTP export omits it, so enriching the export **must add `status`**
   (and `enrollment_type`) — not optional.

### Student_Enrollment field resolution (Finalsite API → Focus SFTP — chosen design)

This is the **chosen** path (Fork 1 = API; contacts via Focus SFTP). It
**sidesteps the API enrollment-write gap** — the Focus SFTP `STUDENT_ENROLLMENT`
template does the enrollment write. Field-by-field, validated live against
Miami:

| Focus field                     | Source                                                                                                      | Remaining                                                          |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `SYEAR` (req)                   | API `school_year.start_year` ✓                                                                              | none                                                               |
| `STUDENT_ID` (req)              | API `id_attributes` (returning) / mint (new)                                                                | minting authority (★ gate)                                         |
| `GRADE_ID` (req)                | API `grade.canonical_name` ✓                                                                                | Finalsite-grade → Focus Short-Name map; Focus grade levels set up  |
| `SCHOOL_ID` (req)               | API `assigned_school_ss` (Miami, confirmed) ✓                                                               | Finalsite-school → Focus `SCH_ID` crosswalk; Focus Schools exist   |
| `START_DATE` (req)              | **`stg_finalsite__status_report.enrolled_date`** (join `finalsite_enrollment_id`) ✓                         | none — sourced                                                     |
| `ENROLLMENT_CODE` (opt, needed) | derive from API `status` / `enrollment_type`                                                                | `new`/`returning` → Focus Add-code (`EA1`/`RA1`) map; codes set up |
| `END_DATE` + `DROP_CODE` (xfer) | status-report withdrawal dates (`mid_year_withdrawal_date` / `summer_withdraw_date` / `not_enrolling_date`) | reason → Focus `DROP_CODE` map                                     |
| `CALENDAR_ID` (opt)             | blank = school default                                                                                      | only if non-default calendars                                      |

**Every required field is now sourced — no data gaps.** The API supplies the
contact-side fields; the already-ingested Status Report supplies the workflow
dates (`enrolled_date` = `START_DATE`, withdrawal dates for transfer-out),
joined on `finalsite_enrollment_id` (= API `contact.id`). What remains is
**mapping + Focus-side setup**, not data availability:

1. **Mapping**: Finalsite grade → Focus Short-Name; `assigned_school_ss` → Focus
   `SCH_ID`; `status`/`enrollment_type` → `ENROLLMENT_CODE`; withdrawal reason →
   `DROP_CODE`.
2. **Focus code setup** (must exist, case-sensitive short names): Grade Levels,
   Enrollment Codes (Add + Drop), Calendars, Schools.
3. **`STUDENT_ID` minting (★ gate)** — the only open item: returning students
   match an existing number; new students need one minted (autogen `IdField`
   pending Finalsite).

## Finalsite API live profile (Newark proxy, n=300)

Profiled the **live** Finalsite Enrollment API for **Newark** (same product as
Miami; aggregates only, no PII) to ground the API-source assumptions. Newark is
a **proxy**: status stages, the `IdField` mechanism, grades, and relationship
types should transfer, but the specific **custom-field names** and which
`IdField` holds the canonical number are per-tenant — Miami needs its own pass
once Miami API creds exist (Newark's IdFields are
PowerSchool/FACTS/Blackbaud/Veracross — no Focus field).

- **The API is far richer than the export** (599 fields). Populated custom/track
  fields include `race_ms`, **`kipp_school_2025_2026_ss` +
  `assigned_school_ss`** (school-of-enrollment), `media_release_yn`,
  `preferred_language_txt`, a full medical set, IEP/504/SpEd, **four emergency
  contacts** (`emrg_1..4_*`), and `us_school_entry_date`. Everything the export
  would need to add already exists.
- **No autogen `IdField` today** — all 7 are `autogen=False` passthroughs
  (`powerschool_student_number`, `facts_sis_student_id` = `STU…pad_zeroes:12`):
  SIS-minted values written back, not Finalsite-generated. The formatting engine
  is present, so an autogen field is feasible (see _minting gate_).
- **Identity populated only for returning students** — `id_attributes` carries
  the SIS number for **205/205 returning** and **0/44 new** (by status:
  `enrolled` 182/203, `not_enrolling` 13/14, all inquiry/waitlist/applicant 0).
- **Eligibility predicate** — 25-status catalog; active accepted→enrolled
  (`accepted`/`enrollment_in_progress`/`assigned_school`/`enrolled`/`retained`)
  = in-scope; `enrollment_type` (returning 205 / new 44) drives re-enroll vs
  create.
- **Siblings direct** — `relationships`: parent 382, **sibling 183**,
  grandparent 41 → `Linked_Students` from the API, no inference.

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
- **The SFTP export already reserves SIS-ID slots** (`PowerSchool DCID` /
  `Student Number` at student level, `PowerSchool Contact ID` per guardian) —
  mostly empty, but a few guardian rows carry a value, evidence the write-back
  target field exists and is partially populated. Whether these slots are the
  intended Focus write-back targets (mislabeled), vestigial PowerSchool-template
  columns, or real PowerSchool IDs is the _SIS-ID column gate_ — it determines
  what the crosswalk anchors on from the source side and where write-back lands.
- **Match-vs-mint is empirically clean (Newark live profile).** The SIS number
  is present for **100% of returning** students (205/205) and **0% of new**
  (0/44) — so resolution is binary: returning → match the number already in
  Finalsite's `id_attributes`; new → mint + write back. That write-back is the
  manual step the integration replaces.

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
only. Counts/aggregates are fine; identifiers are not. The SFTP export sample is
held in Drive and is **not committed** to the repo.

The export adds **medical PII** (student doctor name/phone, preferred hospital,
hospital phone) on top of names, DOB, address, and guardian contacts. If the
medical-destination gate resolves to "out of scope," drop these columns at
staging so they never enter the warehouse rather than carrying and ignoring
them.

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

   **Live evidence (Newark profile).** No `IdField` uses `autogen=True` today
   (all 7 are passthrough), and `id_attributes` is populated only for
   **returning** students (205/205), **0/44 new** — the number is written back
   **manually today** and undone for new enrollees. **KTAF is in active
   discussion with Finalsite about adding an autogen `IdField`** (option **a**);
   the formatting engine is confirmed present (e.g.
   `STU{{ value | … | pad_zeroes: 12 }}`), so 1a is viable pending Finalsite's
   answers on counter scope/uniqueness, template tokens, 10-digit match, and
   admin setup. Under 1a the integration just **reads** the generated id and
   pushes to Focus — no pipeline minting and no number write-back.

   Identity-resolution absorbs whichever via one config flag. Formal ownership
   sign-off: Miami ops / central data.

2. **Fork 1 — RESOLVED → REST API** (live-validated 2026-06-09; see _Fork 1_).
   `enrolled_date` / lifecycle dates join from `stg_finalsite__status_report`.
3. **Fork 2** — Focus transport (SFTP vs API). The all-guardians decision rules
   out API-only for contacts; remaining choice is for the student/enrollment
   records, gated on the API vendor-confirm items below.

   **Enrollment-data gate — RESOLVED (2026-06-09).** Fork 1 sources from the
   **API**, which natively carries `status` / `enrollment_type` / `grade` /
   `school_year` / `relationships` plus race / school / medical as custom fields
   (validated live against Miami). `enrolled_date` (`START_DATE`), the
   eligibility status timeline, and transfer-out withdrawal dates come from the
   already-ingested **`stg_finalsite__status_report`**, joined on
   `finalsite_enrollment_id` (= API `contact.id`). No export reconfiguration
   needed; the new "Focus Student Export" file is not used as a source.

   **★ SIS-ID column gate** — _confirm with:_ the Finalsite export owner.
   _Question:_ are the PowerSchool-named SIS-ID slots a cloned PowerSchool
   template (vestigial for Focus), the intended Focus write-back targets, or
   real PowerSchool IDs? _Decides:_ source-side crosswalk anchor and the
   write-back target field.

   **Medical-destination gate** — _confirm with:_ Miami ops. _Question:_ is
   Focus the home for doctor/hospital/media-release data? _Decides:_ whether to
   map the medical columns into Focus or drop them at staging (preferred default
   if unconfirmed, to limit medical PII).

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
   codes (grades, enrollment codes, calendars) exist. Guardian cardinality is
   **decided** — preserve all (source supplies up to 4), so contacts go via the
   SFTP `Contacts` template (API caps at 2).

## Out of scope

Two-way **data** sync (Focus → Finalsite beyond writing the resolved id back);
non-Miami regions; migrating the existing cohort (already done); the inbound
Focus → warehouse load (separate spec). Note: ongoing updates, transfers-out,
re-enrollment, and contacts are explicitly **in** scope (Finalsite → Focus) —
see _Sync operations_.
