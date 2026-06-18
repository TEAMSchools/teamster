# Focus Staging — Students / People (Batch A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add contract-enforced `stg_focus__*` staging models for the three
populated Focus students/people tables (`address`, `people_join_contacts`,
`students`) in the `focus` source-system dbt project.

**Architecture:** One staging model + properties YAML per source table, reading
the BQ-native Focus dlt source already declared in
`src/dbt/focus/models/staging/sources-bigquery.yml`. Light cleaning only:
explicit column projection (drop dlt bookkeeping + audit-quad columns), a
soft-delete filter where the table has a `deleted` flag, a uniqueness test on
each table's primary key, and a `description:` on the model and every column.
Two of the three tables (`address`, `students`) are wide and are curated to a
core column set. `students` additionally projects, INLINE, the currently
populated `custom_*` columns under their human-readable slugs (from the
pre-generated custom-field map), aliased but otherwise passed through as stored
codes. Models build inside the consuming district project (`kippmiami`), which
sets `focus_schema` and imports the `focus` package.

**Tech Stack:** dbt (BigQuery), `dbt_utils`, dbt contracts. SQL per
`.trunk/config/.sqlfluff` (BigQuery dialect, trailing commas, single quotes, 88
cols, lowercase).

## Global Constraints

- Contract enforcement is already set at the `staging` directory level in
  `src/dbt/focus/dbt_project.yml` (`+contract: enforced: true`) — do NOT add
  `{{ config(contract=...) }}` per model. Every column the SQL projects MUST be
  declared in the properties YAML with a matching `data_type`.
- Source is BQ-native: `{{ source("focus", "<table>") }}` (source name `focus`,
  bare table name). Schema resolves from `var("focus_schema")` =
  `dagster_kippmiami_dlt_focus` (set in `src/dbt/kippmiami/dbt_project.yml`).
- Exclude dlt bookkeeping columns (`_dlt_id`, `_dlt_load_id`) and the audit-quad
  (`created_by_class`, `created_by_id`, `updated_by_class`, `updated_by_id`)
  from every model. Keep `created_at` / `updated_at` / `uuid`.
- Staging uniqueness + `not_null` tests MUST set `config: severity: error`
  (project default is `warn`).
- **Soft-delete:** `address` and `students` have a `deleted INT64` column that
  is `NULL` for live rows and `1` for deleted — there is no `0`. Add
  `where deleted is null` (NULL = live; never `= 0`, which matches nothing) and
  OMIT the `deleted` column from the projection — its value is predetermined by
  the filter. `people_join_contacts` has no soft-delete column, so no filter.
- **Wide-table curation:** `students` (565 columns) and `address` (74 columns)
  carry a curated core column set. `address` is curated to its core columns
  only. `students` additionally projects the currently-populated `custom_*`
  columns INLINE under their human-readable slugs (see "Inline custom-field
  projection" below); the unpopulated `custom_*` long-tail and the `search_*` /
  `application_*` denormalized copies stay out of the projection.
- **Inline custom-field projection (`students` only):** the populated `custom_*`
  columns are projected `<column_name> as <slug>` immediately after the curated
  core columns, before any cast block (ST06 — these are plain renamed column
  refs, so they sit in the first ST06 group with the rest of the column
  enumeration). The exact `column_name → slug → data_type` set is fixed by the
  pre-generated map and is enumerated in full in Task 3. Add ONLY the columns in
  that map (the currently-populated set); do NOT add any other `custom_*`
  column.
- **Custom values stay encoded.** `select` / `multiple` / `checkbox` custom
  values remain the raw stored codes (integer option ids, etc.) — they are NOT
  decoded to their option labels in this batch. Code-to-label decoding against
  the `custom_fields` / `custom_field_select_options` catalog is a deferred
  follow-up.
- Focus columns are already `snake_case`. No reserved-word column names appear
  in the curated sets or in the custom-field slugs for these three tables, so no
  backtick-quoting / `quote: true` is needed (the custom columns DO use `as`
  aliasing to rename `custom_*` to its slug; the curated core columns do not
  alias).
- Y/N-style flags (`unlisted`, `blocked`, `callout`, `force_password_change`,
  etc.) stay raw `STRING` in staging — no `is_` boolean conversion in this batch
  (convert in an intermediate layer later if a consumer needs it).
- `address` and `students` both carry credential / auth columns (`password`,
  `username`, `force_password_change`, `last_login`, `failed_login`,
  `force_logout`, `password_token`). These are credential PII, are not in the
  FLDOE import-layout mapping, and no downstream consumer needs them — they are
  intentionally excluded from the curated projection. Do not add them.
- Build/test context is the **kippmiami** project, not `focus` standalone:
  `uv run dbt build --select <model> --project-dir src/dbt/kippmiami`.

---

## Setup (once, before Task 1)

- [ ] **Install package deps in the worktree** (fresh worktrees have no
      `dbt_packages/`):

```bash
uv run dbt deps --project-dir src/dbt/kippmiami
```

Expected: `Installed N packages` (no "0 package(s) installed" error).

---

### Task 1: `stg_focus__people_join_contacts`

The narrowest of the three tables (18 source columns, no soft-delete, no
`custom_*`). Build it first to prove the pattern before the wide tables. Grain
is one row per contact-detail record (`id`); `people_join_contacts` links a
person to a single contact detail (phone / email / etc.), with `value` holding
the contact value and `title` the contact-type label.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__people_join_contacts.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__people_join_contacts.yml`

**Interfaces:**

- Consumes: `source("focus", "people_join_contacts")`
- Produces: model `stg_focus__people_join_contacts`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

Keep every non-excluded column (drop only `_dlt_*` and the audit-quad
`created_by_class` / `created_by_id` / `updated_by_class` / `updated_by_id`).

```sql
select
    id,
    person_id,
    detail_priority,
    title,
    value,
    imported,
    unlisted,
    callout,
    blocked,
    sms,
    unsubscribe,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "people_join_contacts") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__people_join_contacts
    description: >-
      Focus person-to-contact-detail link — one row per contact detail (phone,
      email, etc.) attached to a person. `value` holds the contact value and
      `title` the contact-type label.
    columns:
      - name: id
        description: Primary key — Focus people-join-contacts id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: person_id
        description: Focus person id this contact detail belongs to.
        data_type: int
      - name: detail_priority
        description: Ordering priority of this contact detail for the person.
        data_type: int
      - name: title
        description: Contact-type label for the detail (e.g. the contact type).
        data_type: string
      - name: value
        description: Contact value (e.g. the phone number or email address).
        data_type: string
      - name: imported
        description: Y/N — whether the contact detail originated from an import.
        data_type: string
      - name: unlisted
        description: Y/N — whether the contact detail is flagged unlisted.
        data_type: string
      - name: callout
        description: Y/N — whether the contact detail is included in callouts.
        data_type: string
      - name: blocked
        description: Y/N — whether the contact detail is blocked.
        data_type: string
      - name: sms
        description: Y/N — whether the contact detail can receive SMS messages.
        data_type: string
      - name: unsubscribe
        description: Y/N — whether the contact has unsubscribed from messaging.
        data_type: string
      - name: uuid
        description: Focus global unique identifier for the row.
        data_type: string
      - name: created_at
        description: Row creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Row last-update timestamp in Focus.
        data_type: timestamp
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__people_join_contacts --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` tests on `id` PASS. A contract
mismatch here means a `data_type` in the YAML disagrees with the warehouse — fix
the YAML to match `INFORMATION_SCHEMA.COLUMNS` (all link/priority columns are
`int`, the rest `string`, dates `timestamp`).

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__people_join_contacts.sql src/dbt/focus/models/staging/properties/stg_focus__people_join_contacts.yml
git commit -m "feat(dbt): add stg_focus__people_join_contacts (#4213)"
```

---

### Task 2: `stg_focus__address`

`address` has 74 source columns and a `deleted INT64` soft-delete flag. It is a
generic Focus address/login table; the FLDOE import-layout maps only the address
fields (`address`, `address2`, `city`, `state`, `zipcode`, `phone`, and their
`mail_*` mailing counterparts). Curate to: the keys, the mapped address fields,
the parsed address components, geo coordinates, the messaging/validity flags,
and the audit dates. Drop the `deleted` column (predetermined by the filter),
the audit-quad, the dlt columns, and the credential/auth columns (see Global
Constraints). `address` has no populated custom-field map in this batch, so it
carries no inline `custom_*` block.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__address.sql`
- Create: `src/dbt/focus/models/staging/properties/stg_focus__address.yml`

**Interfaces:**

- Consumes: `source("focus", "address")`
- Produces: model `stg_focus__address`, grain one row per `address_id` (live
  rows only).

- [ ] **Step 1: Write the model SQL**

The `deleted` filter goes in `WHERE`; `deleted` is omitted from the projection.

```sql
select
    address_id,
    profile_id,
    parent_id,
    university_id,
    district_id,
    address,
    address2,
    city,
    state,
    zipcode,
    plus4,
    district,
    country,
    care_of,
    mail_address,
    mail_address2,
    mail_city,
    mail_state,
    mail_zipcode,
    mail_plus4,
    mail_district,
    mail_country,
    mail_care_of,
    number,
    number_suffix,
    direction_prefix,
    street_name,
    street_suffix,
    direction_suffix,
    primary_unit_type,
    primary_unit_number,
    secondary_unit_type,
    secondary_unit_number,
    mail_number,
    mail_number_suffix,
    mail_direction_prefix,
    mail_street_name,
    mail_street_suffix,
    mail_direction_suffix,
    mail_primary_unit_type,
    mail_primary_unit_number,
    mail_secondary_unit_type,
    mail_secondary_unit_number,
    phone,
    latitude,
    longitude,
    address_import_key,
    imported,
    unlisted,
    callout,
    blocked,
    sms,
    unsubscribe,
    valid,
    usps_valid,
    missing_from_catalog,
    disclaimer_agreement,
    last_change,
    parsed_at,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "address") }}
where deleted is null
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__address
    description: >-
      Focus address records (live rows only) — one row per address id. Carries
      the primary and mailing address, parsed USPS address components, geo
      coordinates, and validity/messaging flags. Soft-deleted rows are excluded
      and the `custom_*` long-tail is not part of this table.
    columns:
      - name: address_id
        description: Primary key — Focus address id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: profile_id
        description: Focus profile id the address is attached to.
        data_type: int
      - name: parent_id
        description:
          Parent address id, when the row is a derived/linked address.
        data_type: int
      - name: university_id
        description: Focus university id associated with the address.
        data_type: int
      - name: district_id
        description: Focus district id.
        data_type: int
      - name: address
        description: Street address line 1.
        data_type: string
      - name: address2
        description: Street address line 2.
        data_type: string
      - name: city
        description: City of the address.
        data_type: string
      - name: state
        description: State of the address.
        data_type: string
      - name: zipcode
        description: ZIP code of the address.
        data_type: string
      - name: plus4
        description: ZIP+4 extension of the address.
        data_type: string
      - name: district
        description: District text value associated with the address.
        data_type: string
      - name: country
        description: Country of the address.
        data_type: string
      - name: care_of
        description: Care-of (c/o) line for the address.
        data_type: string
      - name: mail_address
        description: Mailing address line 1.
        data_type: string
      - name: mail_address2
        description: Mailing address line 2.
        data_type: string
      - name: mail_city
        description: Mailing city.
        data_type: string
      - name: mail_state
        description: Mailing state.
        data_type: string
      - name: mail_zipcode
        description: Mailing ZIP code.
        data_type: string
      - name: mail_plus4
        description: Mailing ZIP+4 extension.
        data_type: string
      - name: mail_district
        description: Mailing district text value.
        data_type: string
      - name: mail_country
        description: Mailing country.
        data_type: string
      - name: mail_care_of
        description: Mailing care-of (c/o) line.
        data_type: string
      - name: number
        description: Parsed street number of the primary address.
        data_type: int
      - name: number_suffix
        description: Parsed street-number suffix of the primary address.
        data_type: string
      - name: direction_prefix
        description: Parsed leading directional of the primary address.
        data_type: string
      - name: street_name
        description: Parsed street name of the primary address.
        data_type: string
      - name: street_suffix
        description: Parsed street suffix of the primary address.
        data_type: string
      - name: direction_suffix
        description: Parsed trailing directional of the primary address.
        data_type: string
      - name: primary_unit_type
        description: Parsed primary unit type (e.g. apt, suite).
        data_type: string
      - name: primary_unit_number
        description: Parsed primary unit number.
        data_type: string
      - name: secondary_unit_type
        description: Parsed secondary unit type.
        data_type: string
      - name: secondary_unit_number
        description: Parsed secondary unit number.
        data_type: string
      - name: mail_number
        description: Parsed street number of the mailing address.
        data_type: int
      - name: mail_number_suffix
        description: Parsed street-number suffix of the mailing address.
        data_type: string
      - name: mail_direction_prefix
        description: Parsed leading directional of the mailing address.
        data_type: string
      - name: mail_street_name
        description: Parsed street name of the mailing address.
        data_type: string
      - name: mail_street_suffix
        description: Parsed street suffix of the mailing address.
        data_type: string
      - name: mail_direction_suffix
        description: Parsed trailing directional of the mailing address.
        data_type: string
      - name: mail_primary_unit_type
        description: Parsed primary unit type of the mailing address.
        data_type: string
      - name: mail_primary_unit_number
        description: Parsed primary unit number of the mailing address.
        data_type: string
      - name: mail_secondary_unit_type
        description: Parsed secondary unit type of the mailing address.
        data_type: string
      - name: mail_secondary_unit_number
        description: Parsed secondary unit number of the mailing address.
        data_type: string
      - name: phone
        description: Phone number associated with the address.
        data_type: string
      - name: latitude
        description: Geocoded latitude of the address.
        data_type: numeric
      - name: longitude
        description: Geocoded longitude of the address.
        data_type: numeric
      - name: address_import_key
        description: Source import key used to match the address on import.
        data_type: string
      - name: imported
        description: Y/N — whether the address originated from an import.
        data_type: string
      - name: unlisted
        description: Y/N — whether the address is flagged unlisted.
        data_type: string
      - name: callout
        description: Y/N — whether the address is included in callouts.
        data_type: string
      - name: blocked
        description: Y/N — whether the address is blocked.
        data_type: string
      - name: sms
        description: Y/N — whether the address can receive SMS messages.
        data_type: string
      - name: unsubscribe
        description: Y/N — whether the address has unsubscribed from messaging.
        data_type: string
      - name: valid
        description: Y/N — whether the address is marked valid in Focus.
        data_type: string
      - name: usps_valid
        description: Y/N — whether the address passed USPS validation.
        data_type: string
      - name: missing_from_catalog
        description: Y/N — whether the address is missing from the USPS catalog.
        data_type: string
      - name: disclaimer_agreement
        description: Y/N — whether the disclaimer agreement was accepted.
        data_type: string
      - name: last_change
        description: Source last-change timestamp for the address.
        data_type: timestamp
      - name: parsed_at
        description: Timestamp the address was parsed into components.
        data_type: timestamp
      - name: uuid
        description: Focus global unique identifier for the row.
        data_type: string
      - name: created_at
        description: Row creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Row last-update timestamp in Focus.
        data_type: timestamp
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__address --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` tests on `address_id` PASS. Watch
the `int` parsed-number columns (`number`, `mail_number`) and the `numeric` geo
columns (`latitude`, `longitude`) — match the YAML `data_type` to the warehouse
type exactly, or the contract fails. If `unique` on `address_id` fails, do NOT
add dedupe — investigate whether `deleted is null` left genuine duplicates and
raise it as an upstream data question.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__address.sql src/dbt/focus/models/staging/properties/stg_focus__address.yml
git commit -m "feat(dbt): add stg_focus__address (#4213)"
```

---

### Task 3: `stg_focus__students`

`students` is the widest table in the Focus source (565 columns). Roughly 510 of
those are `custom_*` columns and a further block are `search_*` denormalized
copies, `application_*` admissions fields, and credential/auth columns. This
staging model carries the curated core set — the identity keys, the student name
fields, and the row-lifecycle dates/flags — PLUS the currently-populated
`custom_*` columns, projected INLINE under their human-readable slugs.

The populated custom set is exactly the 18 columns in the pre-generated map
(`.claude/scratch/focus-students-custom-map.md`): every other `custom_*` column
is unpopulated and is NOT projected. The custom values are passed through as
their raw stored codes — `select` / `checkbox` custom values stay encoded
(integer option ids, etc.); they are NOT decoded to option labels here. The
remaining unpopulated `custom_*` long-tail and the `search_*` / `application_*`
denormalized copies stay out of the projection.

PK is `student_id`. `deleted INT64` (`NULL` = live, `1` = deleted) is filtered
and omitted.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__students.sql`
- Create: `src/dbt/focus/models/staging/properties/stg_focus__students.yml`

**Interfaces:**

- Consumes: `source("focus", "students")`
- Produces: model `stg_focus__students`, grain one row per `student_id` (live
  rows only).

- [ ] **Step 1: Write the model SQL**

Curated core first, then the populated `custom_*` block aliased to its slugs
(both groups are plain column refs, so they share the first ST06 group; the
custom block follows the core block with a blank line between them).
`student_id` is the PK; `profile_id` is the Focus person identity. Drop
`deleted` (predetermined by the filter), the audit-quad, the dlt columns, the
credential/auth columns, and every `custom_*` / `search_*` / `application_*`
column NOT in the populated map.

```sql
select
    student_id,
    profile_id,
    university_id,
    district_id,
    first_name,
    middle_name,
    last_name,
    name_suffix,
    external_api_uuid,
    protected_student,
    incomplete,
    last_updated_date,
    last_change,
    uuid,
    created_at,
    updated_at,

    custom_53 as local_student_id,
    custom_100000101 as race_asian,
    custom_200000000 as sex,
    custom_100000104 as race_white,
    custom_100000105 as ethnicity_hispanic_or_latino,
    custom_100000100 as race_american_indian_or_alaska_native,
    custom_100000103 as race_native_hawaiian_or_other_pacific_islander,
    custom_200000005 as language,
    custom_100000102 as race_black_or_african_american,
    custom_837 as residence_county,
    custom_200000004 as birthdate,
    custom_861 as florida_alias,
    custom_159 as florida_student_number,
    custom_l1482 as powerschool_id,
    custom_200000012 as student_e_mail_address,
    custom_l1483 as disis_id,
    custom_200000225 as fleid_verified,
    custom_200000224 as florida_education_identifier,
from {{ source("focus", "students") }}
where deleted is null
```

- [ ] **Step 2: Write the properties YAML**

Core columns first (PK tests at the top), then one entry per populated custom
column. Custom `data_type` is the map's `bq_type` mapped to repo spelling
(`STRING` → `string`, `INT64` → `int`, `NUMERIC` → `numeric`, `TIMESTAMP` →
`timestamp`); the description is the map's catalog title.

```yaml
models:
  - name: stg_focus__students
    description: >-
      Focus students — curated core plus the currently-populated custom fields
      (live rows only), one row per student id. Carries identity keys, student
      name, row-lifecycle dates/flags, and the populated `custom_*` columns
      renamed to their human-readable slugs. Custom `select` / `checkbox` values
      remain as the raw stored codes (integer option ids, etc.) — they are not
      decoded to their option labels in this model. Unpopulated `custom_*`
      columns and the `search_*` / `application_*` denormalized copies are not
      projected.
    columns:
      - name: student_id
        description: Primary key — Focus local student id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: profile_id
        description: Focus profile (person) id for the student.
        data_type: int
      - name: university_id
        description: Focus university id associated with the student.
        data_type: int
      - name: district_id
        description: Focus district id.
        data_type: int
      - name: first_name
        description: Student first name.
        data_type: string
      - name: middle_name
        description: Student middle name.
        data_type: string
      - name: last_name
        description: Student last name.
        data_type: string
      - name: name_suffix
        description: Student name suffix.
        data_type: string
      - name: external_api_uuid
        description: External API unique identifier for the student.
        data_type: string
      - name: protected_student
        description: Y/N — whether the student record is access-protected.
        data_type: string
      - name: incomplete
        description: Flag — whether the student record is marked incomplete.
        data_type: int
      - name: last_updated_date
        description: Source last-updated date for the student record.
        data_type: date
      - name: last_change
        description: Source last-change timestamp for the student record.
        data_type: timestamp
      - name: uuid
        description: Focus global unique identifier for the row.
        data_type: string
      - name: created_at
        description: Row creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Row last-update timestamp in Focus.
        data_type: timestamp
      - name: local_student_id
        description: Local Student ID
        data_type: string
      - name: race_asian
        description: Race - Asian
        data_type: int
      - name: sex
        description: Sex
        data_type: int
      - name: race_white
        description: Race - White
        data_type: int
      - name: ethnicity_hispanic_or_latino
        description: Ethnicity - Hispanic or Latino
        data_type: int
      - name: race_american_indian_or_alaska_native
        description: Race - American Indian or Alaska Native
        data_type: int
      - name: race_native_hawaiian_or_other_pacific_islander
        description: Race - Native Hawaiian or Other Pacific Islander
        data_type: int
      - name: language
        description: Language
        data_type: int
      - name: race_black_or_african_american
        description: Race - Black or African American
        data_type: int
      - name: residence_county
        description: Residence County
        data_type: int
      - name: birthdate
        description: Birthdate
        data_type: timestamp
      - name: florida_alias
        description: Florida Alias
        data_type: string
      - name: florida_student_number
        description: Florida Student Number
        data_type: string
      - name: powerschool_id
        description: PowerSchool ID
        data_type: numeric
      - name: student_e_mail_address
        description: Student E-mail Address
        data_type: string
      - name: disis_id
        description: DISIS ID
        data_type: numeric
      - name: fleid_verified
        description: FLEID Verified
        data_type: string
      - name: florida_education_identifier
        description: Florida Education Identifier
        data_type: string
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__students --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` tests on `student_id` PASS. Type
checks to watch against `INFORMATION_SCHEMA.COLUMNS`: `student_id` /
`profile_id` / `university_id` / `district_id` / `incomplete` are `int`;
`last_updated_date` is `date`; `last_change` / `created_at` / `updated_at` are
`timestamp`. For the custom block, the contract `data_type` must match the
warehouse column type of the underlying `custom_*` column, not the slug's
semantic meaning — e.g. `birthdate` (from `custom_200000004`) is `timestamp` in
the warehouse even though it represents a date, and `powerschool_id` /
`disis_id` are `numeric`. If a custom column's contract fails, pull the
underlying `custom_*` column's type verbatim from `INFORMATION_SCHEMA.COLUMNS`
and update the YAML to match. If `unique` on `student_id` fails, do NOT add
dedupe — confirm whether `deleted is null` rows still collide and raise it as an
upstream data question (a real student should be unique by `student_id`).

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__students.sql src/dbt/focus/models/staging/properties/stg_focus__students.yml
git commit -m "feat(dbt): add stg_focus__students (#4213)"
```

---

## Final verification

- [ ] **Build all three together:**

```bash
uv run dbt build --select stg_focus__people_join_contacts stg_focus__address stg_focus__students --project-dir src/dbt/kippmiami
```

Expected: 3 models build, 6 tests (unique + not_null per model) PASS.

- [ ] **Lint the new files** (sqlfluff/yamllint fire at pre-push/CI, not the
      commit hook). Run from inside the worktree:

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/focus/models/staging/stg_focus__people_join_contacts.sql \
  src/dbt/focus/models/staging/stg_focus__address.sql \
  src/dbt/focus/models/staging/stg_focus__students.sql \
  src/dbt/focus/models/staging/properties/stg_focus__people_join_contacts.yml \
  src/dbt/focus/models/staging/properties/stg_focus__address.yml \
  src/dbt/focus/models/staging/properties/stg_focus__students.yml
```

Expected: no sqlfluff / yamllint findings on the six new files.

## Out of scope (other plans / issues)

- **Decoding `select` / `multiple` / `checkbox` custom values** — the populated
  custom columns are projected here as their raw stored codes (integer option
  ids, etc.). Translating those codes to their option labels against the
  `custom_fields` / `custom_field_select_options` catalog is a deferred
  follow-up, not part of this batch.
- The unpopulated `custom_*` long-tail (and the `search_*` / `application_*`
  denormalized copies) — not projected; only the currently-populated custom
  columns in the pre-generated map are added.
- The credential/auth columns on `address` and `students` (`password`,
  `username`, `force_password_change`, `last_login`, `failed_login`,
  `force_logout`, `password_token`) — intentionally dropped; not modeled.
- The `students_join_*` link tables (`students_join_people`,
  `students_join_address`, `students_join_students`) and the `people` table —
  these source tables are empty and are tracked under #4220.
- kipptaf region source + `stg_kippmiami__focus__*` wrappers — deferred to the
  kipptaf-integration plan; add a wrapper only when a mart consumes one of
  these.

## Self-review checklist (run before handing off)

1. **Spec coverage:** all three Batch A tables (`address`,
   `people_join_contacts`, `students`) have a staging task with full SQL + full
   YAML + exact build command. `students` additionally projects all 18 populated
   custom columns inline. ✓
2. **Placeholder scan:** no TBD / TODO / "add appropriate X" — every task is
   complete; the custom block enumerates all 18 columns in both SQL and YAML. ✓
3. **PK + soft-delete:** PKs are `id` (people_join_contacts), `address_id`
   (address), `student_id` (students), each with `unique` + `not_null` at
   `severity: error`. `address` and `students` apply `where deleted is null`
   (NULL = live; not `= 0`) and omit `deleted`; `people_join_contacts` has no
   soft-delete. ✓
4. **Exclusions:** every model drops `_dlt_*` and the audit-quad
   (`created_by_class` / `created_by_id` / `updated_by_class` /
   `updated_by_id`); keeps `created_at` / `updated_at` / `uuid`. Credential/auth
   columns dropped from `address` and `students`. ✓
5. **Wide-table curation + inline custom block:** `students` carries the named
   identity/name/date core columns PLUS the 18 populated `custom_*` columns
   aliased to their slugs (placed after the core block, before any cast, per
   ST06); the unpopulated `custom_*` long-tail and `search_*` / `application_*`
   copies are excluded. `address` curated to import-mapped address fields +
   parsed components + keys + geo + flags + dates (no populated custom map). ✓
6. **Custom values encoded:** `select` / `checkbox` custom values stay as raw
   stored codes; no code-to-label decoding in this batch — stated in the model
   description and the Out-of-scope section. ✓
7. **Custom type mapping:** each custom column's `data_type` is the map's
   `bq_type` in repo spelling (`STRING` → `string`, `INT64` → `int`, `NUMERIC` →
   `numeric`, `TIMESTAMP` → `timestamp`) and matches the underlying `custom_*`
   warehouse type, not the slug's semantics (e.g. `birthdate` → `timestamp`,
   `powerschool_id` / `disis_id` → `numeric`). ✓
8. **No slug collisions:** none of the 18 slugs duplicate a curated core column
   already projected on `students`. ✓
9. **Type consistency:** each core YAML `data_type` matches the warehouse type
   (int / string / numeric / date / timestamp). Re-verify the `int`
   parsed-number columns and `numeric` geo columns on `address`, and the `int` /
   `date` / `timestamp` split on `students`, during build. ✓
10. **No `contract: enforced` per model** — set at directory level; do not
    re-declare. ✓
