# Focus Staging — Users & Permissions (Batch G) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add contract-enforced `stg_focus__*` staging models for the five
populated Focus users/permissions tables (`users`, `user_enrollment`,
`user_profiles`, `permission`, `login_history`) in the `focus` source-system dbt
project.

**Architecture:** One staging model + properties YAML per source table, reading
the BQ-native Focus dlt source already declared in
`src/dbt/focus/models/staging/sources-bigquery.yml`. Light cleaning only:
explicit column projection (drop dlt bookkeeping + audit-quad columns), a
soft-delete filter where the table has a `deleted` column, a uniqueness test on
each table's primary key, and a `description:` on the model and every column.
`users` is a wide table (235 columns, mostly a `custom_*` long-tail) — staging
carries the curated core set (identity, keys, names, dates) **plus an inline
block of every currently-populated `custom_*` column, each aliased to its
human-readable slug** from the extracted `custom_fields` catalog. Unpopulated
`custom_*` columns are out of scope (they hold no data). Select/multiple coded
custom values are left **encoded as stored codes** in this batch; decoding
against the `custom_fields` option catalog is a deferred follow-up. Models build
inside the consuming district project (`kippmiami`), which sets `focus_schema`
and imports the `focus` package.

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
- Exclude dlt bookkeeping columns (`_dlt_*`) and the audit-quad
  (`created_by_class`, `created_by_id`, `updated_by_class`, `updated_by_id`)
  from every model. Keep `created_at` / `updated_at` / `uuid`.
- Staging uniqueness + `not_null` tests MUST set `config: severity: error`
  (project default is `warn`).
- **Soft-delete:** Focus `deleted INT64` is `NULL` for live rows and `1` for
  deleted — there is no `0`. Filter `where deleted is null` (NOT `= 0`, which
  matches nothing) and OMIT the `deleted` column from the projection. Only
  `users` in this batch has a `deleted` column. `user_profiles` has an
  `inactive STRING` flag — that is NOT a soft-delete sentinel; keep it as a raw
  attribute column (do not filter on it).
- **Primary keys (uniqueness + `not_null`, both `severity: error`):** `users` →
  `profile_id`; `user_enrollment` → `id`; `user_profiles` → `id`; `permission` →
  `id`; `login_history` → `id`.
- Focus columns are already `snake_case`. No BigQuery-reserved-word column names
  ship in any of the five curated projections, so no backtick-quoting /
  `quote: true` is needed. (`type`, `key`, `date` are projected — they are NOT
  reserved as bare column identifiers in BigQuery and ship unquoted, matching
  the Batch C `school_periods` / `attendance_codes` precedent where `type` ships
  unquoted.)
- Y/N-style flags stay raw `STRING`; coded `INT64` lookups stay raw `INT64`. No
  `is_` boolean conversion in this batch (convert in an intermediate layer later
  if a consumer needs it).
- **Populated custom-field block (`users` only):** every currently-populated
  `custom_*` column is projected as `<column_name> as <slug>` and contracted
  under its slug name. Coded values (`select` / `multiple` focus types) are kept
  as their **stored codes** — decoding them against the `custom_fields` option
  catalog is a deferred follow-up, NOT part of this batch. The authoritative
  list of populated custom columns + their slugs, BigQuery types, and titles is
  `/.claude/scratch/focus-users-custom-map.md`. Do NOT project a custom column
  absent from that map (unpopulated = out of scope) and do NOT duplicate a
  column already in the curated core projection.
- **PII:** several `users` columns are direct PII (`password`,
  `social_security_number` = SSN, `e_mail_address` = email, `first_name` /
  `last_name` / `middle_name`, `ein`). They are projected into staging (staging
  mirrors the source) but never echo a sampled value into any external surface
  (PR, commit, issue). Validation output stays local.
- Build/test context is the **kippmiami** project, not `focus` standalone.

---

## Setup (once, before Task 1)

- [ ] **Install package deps in the worktree** (fresh worktrees have no
      `dbt_packages/`):

```bash
uv run dbt deps --project-dir src/dbt/kippmiami
```

---

### Task 1: `stg_focus__user_profiles`

Narrow lookup table (16 columns). Drops the audit-quad; keeps everything else,
including the `inactive` STRING flag (a raw attribute, not a soft-delete
sentinel). This is the smallest table with no soft-delete — a good
pattern-proving first task for the batch.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__user_profiles.sql`
- Create: `src/dbt/focus/models/staging/properties/stg_focus__user_profiles.yml`

**Interfaces:**

- Consumes: `source("focus", "user_profiles")`
- Produces: model `stg_focus__user_profiles`, grain one row per `id` (a Focus
  permission profile / role definition).

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    district_id,
    profile,
    title,
    type,
    super_profile,
    description,
    inactive,
    imported,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "user_profiles") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__user_profiles
    description: >-
      Focus user profiles — one row per permission profile (role) definition.
      Profiles group users and drive the permission keys in
      stg_focus__permission.
    columns:
      - name: id
        description: Primary key — Focus user profile id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: district_id
        description: Focus district id the profile belongs to.
        data_type: int
      - name: profile
        description: Profile name.
        data_type: string
      - name: title
        description: Display title for the profile.
        data_type: string
      - name: type
        description: Profile type classification (e.g. staff, parent, student).
        data_type: string
      - name: super_profile
        description: Parent / super profile this profile inherits from.
        data_type: string
      - name: description
        description: Free-text description of the profile.
        data_type: string
      - name: inactive
        description:
          Y/N — whether the profile is inactive (raw flag, not a delete
          sentinel).
        data_type: string
      - name: imported
        description: Source import marker for the profile row.
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
`uv run dbt build --select stg_focus__user_profiles --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` tests on `id` PASS. A contract
mismatch here means a `data_type` in the YAML disagrees with the warehouse — fix
the YAML to match `INFORMATION_SCHEMA.COLUMNS`.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__user_profiles.sql src/dbt/focus/models/staging/properties/stg_focus__user_profiles.yml
git commit -m "feat(dbt): add stg_focus__user_profiles (#4213)"
```

---

### Task 2: `stg_focus__permission`

Narrow join table (9 columns). After dropping the audit-quad, five columns
remain. Grain is one permission key per profile.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__permission.sql`
- Create: `src/dbt/focus/models/staging/properties/stg_focus__permission.yml`

**Interfaces:**

- Consumes: `source("focus", "permission")`
- Produces: model `stg_focus__permission`, grain one row per `id` (a single
  permission key granted to a profile).

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    profile_id,
    key,
    created_at,
    updated_at,
from {{ source("focus", "permission") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__permission
    description: >-
      Focus permission grants — one row per permission key granted to a user
      profile. Joins to stg_focus__user_profiles on profile_id.
    columns:
      - name: id
        description: Primary key — Focus permission grant id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: profile_id
        description: Focus user profile id this permission is granted to.
        data_type: int
      - name: key
        description: Permission key string identifying the granted capability.
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
`uv run dbt build --select stg_focus__permission --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__permission.sql src/dbt/focus/models/staging/properties/stg_focus__permission.yml
git commit -m "feat(dbt): add stg_focus__permission (#4213)"
```

---

### Task 3: `stg_focus__login_history`

Narrow audit table (10 columns). No audit-quad and no `deleted` column, so all
ten columns are projected. `date` is a TIMESTAMP column despite the name; keep
the source name. `failed` is a Y/N STRING flag.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__login_history.sql`
- Create: `src/dbt/focus/models/staging/properties/stg_focus__login_history.yml`

**Interfaces:**

- Consumes: `source("focus", "login_history")`
- Produces: model `stg_focus__login_history`, grain one row per `id` (a single
  login / authentication attempt).

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    object_id,
    date,
    type,
    failed,
    ip_address,
    user_agent,
    username,
    token_type,
    hostname,
from {{ source("focus", "login_history") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__login_history
    description: >-
      Focus login history — one row per authentication attempt, including the
      acting user, source IP, and whether the attempt failed.
    columns:
      - name: id
        description: Primary key — Focus login history id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: object_id
        description: Focus id of the user (or object) the login attempt targets.
        data_type: int
      - name: date
        description:
          Timestamp of the login attempt (TIMESTAMP despite the name).
        data_type: timestamp
      - name: type
        description: Login event type classification.
        data_type: string
      - name: failed
        description: Y/N — whether the login attempt failed.
        data_type: string
      - name: ip_address
        description: Source IP address of the login attempt.
        data_type: string
      - name: user_agent
        description: Client user-agent string for the login attempt.
        data_type: string
      - name: username
        description: Username supplied for the login attempt.
        data_type: string
      - name: token_type
        description: Authentication token type used.
        data_type: string
      - name: hostname
        description: Hostname the login attempt was made against.
        data_type: string
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__login_history --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__login_history.sql src/dbt/focus/models/staging/properties/stg_focus__login_history.yml
git commit -m "feat(dbt): add stg_focus__login_history (#4213)"
```

---

### Task 4: `stg_focus__user_enrollment`

Narrow table (21 columns). After dropping the audit-quad, 17 columns remain.
Several columns are STRING-serialized arrays (`profiles`, `schools`,
`districts`, `schools_array`, `profiles_array`) — keep them raw STRING in
staging; parsing/exploding belongs in an intermediate layer if a consumer needs
it. Note that `imported` and `imported1` are distinct source columns; keep both.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__user_enrollment.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__user_enrollment.yml`

**Interfaces:**

- Consumes: `source("focus", "user_enrollment")`
- Produces: model `stg_focus__user_enrollment`, grain one row per `id` (a
  staff-to-school/profile enrollment span).

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    staff_id,
    profiles,
    schools,
    districts,
    schools_array,
    profiles_array,
    erp_profiles,
    one_access_request_id,
    comment,
    imported,
    imported1,
    start_date,
    end_date,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "user_enrollment") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__user_enrollment
    description: >-
      Focus user enrollments — one row per staff enrollment span linking a staff
      member to the schools, districts, and profiles they are enrolled in for a
      date range. Array-like columns are kept as raw serialized strings.
    columns:
      - name: id
        description: Primary key — Focus user enrollment id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: staff_id
        description: Focus staff id (users.staff_id) this enrollment is for.
        data_type: int
      - name: profiles
        description: Serialized list of profile ids for the enrollment (raw).
        data_type: string
      - name: schools
        description: Serialized list of school ids for the enrollment (raw).
        data_type: string
      - name: districts
        description: Serialized list of district ids for the enrollment (raw).
        data_type: string
      - name: schools_array
        description: Serialized array form of the enrollment's school ids (raw).
        data_type: string
      - name: profiles_array
        description:
          Serialized array form of the enrollment's profile ids (raw).
        data_type: string
      - name: erp_profiles
        description:
          Serialized list of ERP profile ids for the enrollment (raw).
        data_type: string
      - name: one_access_request_id
        description: OneAccess provisioning request id tied to the enrollment.
        data_type: string
      - name: comment
        description: Free-text comment on the enrollment.
        data_type: string
      - name: imported
        description: Source import marker for the enrollment row.
        data_type: string
      - name: imported1
        description: Secondary source import marker for the enrollment row.
        data_type: string
      - name: start_date
        description: First date of the enrollment span.
        data_type: date
      - name: end_date
        description: Last date of the enrollment span.
        data_type: date
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
`uv run dbt build --select stg_focus__user_enrollment --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__user_enrollment.sql src/dbt/focus/models/staging/properties/stg_focus__user_enrollment.yml
git commit -m "feat(dbt): add stg_focus__user_enrollment (#4213)"
```

---

### Task 5: `stg_focus__users`

`users` is the wide table — 235 columns, the vast majority a `custom_*`
long-tail. Staging carries two blocks:

1. The **curated core set**: identity/keys, names, login/identity attributes,
   and the canonical date/timestamp columns.
2. The **populated custom-field block**: every `custom_*` column that currently
   holds data, projected as `<source_column> as <slug>` where the slug is the
   human-readable name from the extracted `custom_fields` catalog. The
   authoritative list is `/.claude/scratch/focus-users-custom-map.md` (10
   populated custom columns of 93 total). Unpopulated `custom_*` columns are out
   of scope here — they hold no data and are not projected.

The custom block sits **after the core columns and before any cast block**
(there are no casts in this model — all columns ship as plain refs — so the
custom block is simply the last group of plain refs before `from`), per ST06.

**Encoding note:** the `active` (`custom_319000004`),
`profile_on_non_production_sites` (`custom_l790`), and `education` (`custom_2`)
columns are `select` / `multiple` focus types. Their values remain **stored
codes** in this staging model — decoding them to labels against the
`custom_fields` option catalog is a deferred follow-up, not part of this batch.

Soft-delete applies: `users.deleted` is `NULL` for live rows and `1` for
deleted. The model filters `where deleted is null` and OMITS the `deleted`
column.

**Curation note — GENDER mapping discrepancy:** an external import-layout
mapping lists `GENDER` → `users.custom_59`, but `custom_59` does NOT exist in
the warehouse `users` schema (and is not in the populated-custom map). The
schema instead has a named `gender INT64` column. This plan projects the named
`gender` column and does not project a (nonexistent) `custom_59`.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__users.sql`
- Create: `src/dbt/focus/models/staging/properties/stg_focus__users.yml`

**Interfaces:**

- Consumes: `source("focus", "users")`
- Produces: model `stg_focus__users`, grain one row per `profile_id` (a Focus
  staff/user account); curated core columns plus the populated custom-field
  slugs.

- [ ] **Step 1: Write the model SQL**

The column order follows ST06 (plain refs only here — no casts/functions): keys,
identity/login, names, school/org context, then the populated custom-field block
(each `custom_*` aliased to its slug), then the canonical dates. The soft-delete
filter lives in `WHERE`.

```sql
select
    profile_id,
    staff_id,
    parent_id,
    rollover_id,
    erp_profile_id,
    university_id,
    current_school_id,
    current_district_id,
    district_id,
    syear,
    username,
    password,
    profile,
    title,
    ein,
    gender,
    first_name,
    middle_name,
    last_name,
    name_suffix,
    homeroom,
    custom_100000001 as e_mail_address,
    custom_200000001 as staff_number_identifier_local,
    custom_100000002 as phone_number,
    custom_200000002 as experience_length_years,
    custom_556 as social_security_number,
    custom_319000004 as active,
    custom_l801 as w4_allowances_under_17,
    custom_l802 as f_3_claim_dependent_and_other,
    custom_l790 as profile_on_non_production_sites,
    custom_2 as education,
    uuid,
    last_login,
    last_change,
    last_updated_date,
    created_at,
    updated_at,
from {{ source("focus", "users") }}
where deleted is null
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__users
    description: >-
      Focus users — one row per active staff/user account (deleted rows
      excluded). Carries the curated core columns (identity, names, school/org
      context, canonical dates) plus every currently-populated custom field,
      each aliased to its human-readable slug from the custom_fields catalog.
      Select/multiple custom values remain as stored codes — decoding them to
      labels is a deferred follow-up. Unpopulated custom_* columns are out of
      scope.
    columns:
      - name: profile_id
        description: Primary key — Focus user account profile id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: staff_id
        description: Focus staff id (links to user_enrollment.staff_id).
        data_type: int
      - name: parent_id
        description: Parent user id, where the account is linked to another.
        data_type: int
      - name: rollover_id
        description: Source user id this account rolled over from.
        data_type: int
      - name: erp_profile_id
        description: ERP profile id linked to this user account.
        data_type: int
      - name: university_id
        description: University / external institution id for the user.
        data_type: int
      - name: current_school_id
        description: Focus school id the user is currently assigned to.
        data_type: int
      - name: current_district_id
        description: Focus district id the user is currently assigned to.
        data_type: int
      - name: district_id
        description: Focus district id that owns the user record.
        data_type: int
      - name: syear
        description: Focus school year (start year, e.g. 2025 = 2025-26).
        data_type: int
      - name: username
        description: Login username for the account.
        data_type: string
      - name: password
        description: Stored password value (PII — never echo a sampled value).
        data_type: string
      - name: profile
        description: Profile name string for the user.
        data_type: string
      - name: title
        description: User title / job title.
        data_type: string
      - name: ein
        description: Employer identification / employee number (EIN) — PII.
        data_type: string
      - name: gender
        description: Coded gender value for the user.
        data_type: int
      - name: first_name
        description: User first name (PII).
        data_type: string
      - name: middle_name
        description: User middle name (PII).
        data_type: string
      - name: last_name
        description: User last name (PII).
        data_type: string
      - name: name_suffix
        description: User name suffix (e.g. Jr., III).
        data_type: string
      - name: homeroom
        description: Homeroom assignment label for the user.
        data_type: string
      - name: e_mail_address
        description: E-mail Address (populated custom field) — PII.
        data_type: string
      - name: staff_number_identifier_local
        description:
          Staff Number Identifier, Local (populated custom field) — PII.
        data_type: string
      - name: phone_number
        description: Phone Number (populated custom field) — PII.
        data_type: string
      - name: experience_length_years
        description: Experience Length (Years) (populated custom field).
        data_type: numeric
      - name: social_security_number
        description: Social Security Number (populated custom field) — PII.
        data_type: string
      - name: active
        description:
          Active (populated custom field) — select-coded; value left as the
          stored code.
        data_type: int
      - name: w4_allowances_under_17
        description: W4 Allowances Under 17 (populated custom field).
        data_type: numeric
      - name: f_3_claim_dependent_and_other
        description: 3 Claim Dependent and Other (populated custom field).
        data_type: numeric
      - name: profile_on_non_production_sites
        description:
          Profile On Non-Production Sites (populated custom field) —
          select-coded; value left as the stored code.
        data_type: int
      - name: education
        description:
          Education (populated custom field) — multiple-select coded; value left
          as the stored code(s).
        data_type: string
      - name: uuid
        description: Focus global unique identifier for the row.
        data_type: string
      - name: last_login
        description: Timestamp of the user's last login.
        data_type: timestamp
      - name: last_change
        description: Timestamp of the last change to the user record.
        data_type: timestamp
      - name: last_updated_date
        description: Source last-updated date for the user record.
        data_type: date
      - name: created_at
        description: Row creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Row last-update timestamp in Focus.
        data_type: timestamp
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__users --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` on `profile_id` PASS. Watch two
failure modes: (a) a contract `data_type` mismatch — confirm each YAML type
against the warehouse. From the populated-custom map the custom types are:
`experience_length_years` / `w4_allowances_under_17` /
`f_3_claim_dependent_and_other` are `numeric`; `active` /
`profile_on_non_production_sites` are `int`; the rest of the custom block is
`string`. In the core block, `gender` is `int` and `last_updated_date` is
`date`, not `timestamp`. (b) a `unique` failure on `profile_id` would mean
deleted rows leaked — confirm the `where deleted is null` filter is present.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__users.sql src/dbt/focus/models/staging/properties/stg_focus__users.yml
git commit -m "feat(dbt): add stg_focus__users (#4213)"
```

---

## Final verification

- [ ] **Build all five together:**

```bash
uv run dbt build --select stg_focus__user_profiles stg_focus__permission stg_focus__login_history stg_focus__user_enrollment stg_focus__users --project-dir src/dbt/kippmiami
```

Expected: 5 models build, 10 tests (unique + not_null per model) PASS.

- [ ] **Lint the new files** (sqlfluff/yamllint fire at pre-push/CI, not the
      commit hook):

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/focus/models/staging/stg_focus__user_profiles.sql \
  src/dbt/focus/models/staging/stg_focus__permission.sql \
  src/dbt/focus/models/staging/stg_focus__login_history.sql \
  src/dbt/focus/models/staging/stg_focus__user_enrollment.sql \
  src/dbt/focus/models/staging/stg_focus__users.sql \
  src/dbt/focus/models/staging/properties/stg_focus__user_profiles.yml \
  src/dbt/focus/models/staging/properties/stg_focus__permission.yml \
  src/dbt/focus/models/staging/properties/stg_focus__login_history.yml \
  src/dbt/focus/models/staging/properties/stg_focus__user_enrollment.yml \
  src/dbt/focus/models/staging/properties/stg_focus__users.yml
```

(Run from inside the worktree.)

## Out of scope (other plans / issues)

- **Decoding select/multiple custom values to labels** — `active`,
  `profile_on_non_production_sites`, and `education` keep their stored codes in
  this batch. Joining them to the `custom_fields` option catalog to resolve
  human-readable labels is a deferred follow-up.
- **Unpopulated `custom_*` columns** (83 of the 93 custom columns hold no data)
  — not projected here; revisit only if a future Focus import begins populating
  one.
- kipptaf region source + `stg_kippmiami__focus__*` wrappers — deferred to the
  kipptaf-integration plan; add a wrapper only when a mart consumes one of
  these.
- `is_` boolean conversion of Y/N STRING flags and code-value decoding of the
  `INT64` lookups (`gender`, `active`, `profile_on_non_production_sites`) —
  belongs in an intermediate layer if a consumer needs it.

## Self-review checklist (run before handing off)

1. **Spec coverage:** all five populated Batch G tables (`users`,
   `user_enrollment`, `user_profiles`, `permission`, `login_history`) have a
   staging task. ✓
2. **Placeholder scan:** every task has complete SQL + complete YAML + exact
   build command. No TBD/TODO/"similar to". ✓
3. **PK correctness:** `users` → `profile_id`; the other four → `id`. Each PK
   carries `unique` + `not_null` at `severity: error`. ✓
4. **Soft-delete:** only `users` has `deleted`; it filters
   `where deleted is null` and omits the `deleted` column.
   `user_profiles.inactive` is kept as a raw attribute, not filtered. ✓
5. **Exclusions:** every model drops `_dlt_*` and the audit-quad; keeps
   `created_at` / `updated_at` / `uuid` where present. (`permission`,
   `user_enrollment`, `user_profiles`, `users` have the audit-quad and drop it;
   `login_history` has neither.) ✓
6. **Wide-table custom block:** `users` carries the curated core plus all 10
   populated `custom_*` columns from `focus-users-custom-map.md`, each aliased
   to its slug; no custom column absent from the map is projected, and no slug
   duplicates a core column. Select/multiple values stay as stored codes. ✓
7. **Type consistency:** each YAML `data_type` matches the warehouse type and
   the map's `bq_type` (mapped to repo spelling: STRING→string, INT64→int,
   NUMERIC→numeric, DATE→date, TIMESTAMP→timestamp). Re-verify during build the
   mixed-type columns: custom `numeric` (`experience_length_years`,
   `w4_allowances_under_17`, `f_3_claim_dependent_and_other`) and custom `int`
   (`active`, `profile_on_non_production_sites`); core `gender` = int,
   `last_updated_date` = date. ✓
