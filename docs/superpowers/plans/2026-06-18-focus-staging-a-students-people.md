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
core column set; the `custom_*` long-tail of `students` is explicitly out of
scope (handled by the separate Batch H unpivot). Models build inside the
consuming district project (`kippmiami`), which sets `focus_schema` and imports
the `focus` package.

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
  `where deleted is null` (a `= 0` filter matches nothing) and OMIT the
  `deleted` column from the projection — its value is predetermined by the
  filter. `people_join_contacts` has no soft-delete column, so no filter.
- **Wide-table curation:** `students` (565 columns, ~510 of them `custom_*`) and
  `address` (74 columns) carry only a curated core column set in this batch. The
  `custom_*` long-tail on `students` is OUT OF SCOPE here — it unpivots to a
  long key/value model in **Batch H**, joined to the `custom_fields` metadata
  crosswalk. Do not enumerate `custom_*` columns in these staging models.
- Focus columns are already `snake_case`. No reserved-word column names appear
  in the curated sets for these three tables, so no backtick-quoting /
  `quote: true` and no `as` aliasing is needed.
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
Constraints).

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
copies, `application_*` admissions fields, and credential/auth columns. Per the
batch decision, this staging model carries ONLY the curated core set: the
identity keys, the student name fields, and the row-lifecycle dates/flags. The
`custom_*` long-tail — which is where the FLDOE import layout maps almost every
demographic, ELL, ESE, 504, and federal/state field — is OUT OF SCOPE here and
unpivots to a long key/value model in **Batch H**, joined to the `custom_fields`
metadata crosswalk. Do not enumerate `custom_*`, `search_*`, or `application_*`
columns in this model.

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

Curated core only. `student_id` is the PK; `profile_id` is the Focus person
identity. Names come from the named (non-custom) columns. Drop `deleted`
(predetermined by the filter), the audit-quad, the dlt columns, the
credential/auth columns, and the entire `custom_*` / `search_*` /
`application_*` long-tail.

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
from {{ source("focus", "students") }}
where deleted is null
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__students
    description: >-
      Focus students — curated core (live rows only), one row per student id.
      Carries identity keys, student name, and row-lifecycle dates/flags. The
      `custom_*` field long-tail (demographics, ELL, ESE, 504, federal/state) is
      intentionally excluded here and is unpivoted to a long key/value model in
      a separate batch.
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
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__students --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` tests on `student_id` PASS. Type
checks to watch against `INFORMATION_SCHEMA.COLUMNS`: `student_id` /
`profile_id` / `university_id` / `district_id` / `incomplete` are `int`;
`last_updated_date` is `date`; `last_change` / `created_at` / `updated_at` are
`timestamp`; the rest are `string`. If `unique` on `student_id` fails, do NOT
add dedupe — confirm whether `deleted is null` rows still collide and raise it
as an upstream data question (a real student should be unique by `student_id`).

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

- The `students` `custom_*` field long-tail (and `search_*` / `application_*`
  copies) — unpivoted to a long key/value model in **Batch H**, joined to the
  `custom_fields` / `custom_field_select_options` metadata crosswalk.
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
   YAML + exact build command. ✓
2. **Placeholder scan:** no TBD / TODO / "add appropriate X" — every task is
   complete. ✓
3. **PK + soft-delete:** PKs are `id` (people_join_contacts), `address_id`
   (address), `student_id` (students), each with `unique` + `not_null` at
   `severity: error`. `address` and `students` apply `where deleted is null` and
   omit `deleted`; `people_join_contacts` has no soft-delete. ✓
4. **Exclusions:** every model drops `_dlt_*` and the audit-quad
   (`created_by_class` / `created_by_id` / `updated_by_class` /
   `updated_by_id`); keeps `created_at` / `updated_at` / `uuid`. Credential/auth
   columns dropped from `address` and `students`. ✓
5. **Wide-table curation:** `students` carries only named identity/name/date
   columns; the `custom_*` long-tail is explicitly deferred to Batch H.
   `address` curated to the import-mapped address fields + parsed components +
   keys + geo
   - flags + dates. ✓
6. **Type consistency:** each YAML `data_type` matches the warehouse type pulled
   from `INFORMATION_SCHEMA.COLUMNS` (int / string / numeric / date /
   timestamp). Re-verify the `int` parsed-number columns and `numeric` geo
   columns on `address`, and the `int` / `date` / `timestamp` split on
   `students`, during build. ✓
7. **No `contract: enforced` per model** — set at directory level; do not
   re-declare. ✓
