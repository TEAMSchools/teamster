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
carries only the curated core set (identity, keys, names, dates, plus the
specific `custom_NNN` columns the FLDOE import layout maps to a named field);
the remaining `custom_*` long-tail is out of scope here and unpivots separately
in Batch H. Models build inside the consuming district project (`kippmiami`),
which sets `focus_schema` and imports the `focus` package.

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
- **PII:** several `users` columns are direct PII (`password`, `custom_556` =
  SSN, `custom_100000001` = email, `first_name` / `last_name` / `middle_name`,
  `ein`). They are projected into staging (staging mirrors the source) but never
  echo a sampled value into any external surface (PR, commit, issue). Validation
  output stays local.
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
long-tail plus a Florida-specific HR/charter/certification block that no
downstream layer in this phase consumes. Staging carries only the **curated core
set**: identity/keys, names, login/identity attributes, the canonical
date/timestamp columns, and the 13 specific `custom_NNN` columns that the FLDOE
"Florida K-12 Import Layouts" STAFF*LAYOUT maps to a named import field (their
descriptions below come from that mapping). The remaining
`custom*\*`columns and the FLDOE HR/charter/certification block are **out of scope** — they unpivot to the long key/value model in **Batch H**, joined to the`custom_fields`
metadata crosswalk. Do NOT enumerate them here.

Soft-delete applies: `users.deleted` is `NULL` for live rows and `1` for
deleted. The model filters `where deleted is null` and OMITS the `deleted`
column.

**Curation note — GENDER mapping discrepancy:** the import-layout mapping lists
`GENDER` → `users.custom_59`, but `custom_59` does NOT exist in the warehouse
`users` schema. The schema instead has a named `gender INT64` column. This plan
projects the named `gender` column and does not project a (nonexistent)
`custom_59`. See Open questions.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__users.sql`
- Create: `src/dbt/focus/models/staging/properties/stg_focus__users.yml`

**Interfaces:**

- Consumes: `source("focus", "users")`
- Produces: model `stg_focus__users`, grain one row per `profile_id` (a Focus
  staff/user account); curated columns only.

- [ ] **Step 1: Write the model SQL**

The column order follows ST06 (plain refs only here — no casts/functions): keys,
identity/login, names, school/org context, the mapped `custom_NNN` block,
canonical dates. The soft-delete filter lives in `WHERE`.

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
    custom_200000001,
    custom_100000001,
    custom_100000002,
    custom_100000003,
    custom_200000002,
    custom_200000003,
    custom_556,
    custom_607,
    custom_2,
    custom_20120001,
    custom_20120002,
    custom_20120003,
    custom_20120004,
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
      excluded). Curated core columns only: identity, names, school/org context,
      the FLDOE-mapped custom fields, and canonical dates. The wide custom field
      long-tail and the Florida HR/charter/certification block are out of scope
      here and unpivot in Batch H.
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
      - name: custom_200000001
        description: Staff number identifier, local (FLDOE STAFF_TCHR_ID) — PII.
        data_type: string
      - name: custom_100000001
        description: E-mail address (FLDOE EMAIL) — PII.
        data_type: string
      - name: custom_100000002
        description: Phone number (FLDOE PH_NUM) — PII.
        data_type: string
      - name: custom_100000003
        description: Homeroom number (FLDOE HOMEROOM).
        data_type: string
      - name: custom_200000002
        description: Experience length in years (FLDOE EXPERIENCE_YRS).
        data_type: numeric
      - name: custom_200000003
        description: Florida education identifier (FLDOE FL_ED_ID) — PII.
        data_type: string
      - name: custom_556
        description: Social Security Number (FLDOE SSN) — PII.
        data_type: string
      - name: custom_607
        description:
          Florida educators certificate number (FLDOE FL_ED_CERT_NUM).
        data_type: string
      - name: custom_2
        description: Education — multi-select code list (FLDOE EDUCATION).
        data_type: string
      - name: custom_20120001
        description:
          National board certified teacher checkbox (FLDOE NB_CERT_TCHR).
        data_type: string
      - name: custom_20120002
        description:
          Athletic coaching endorsement checkbox (FLDOE ATHL_COACH_ENDORSE).
        data_type: string
      - name: custom_20120003
        description: Clinical education trained checkbox (FLDOE CLIN_ED_TRAIN).
        data_type: string
      - name: custom_20120004
        description: ELL certification status (FLDOE ELL_CERT_STAT).
        data_type: int
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
against the warehouse (`gender` and `custom_20120004` are `int`;
`custom_200000002` is `numeric`; `last_updated_date` is `date`, not
`timestamp`); (b) a `unique` failure on `profile_id` would mean deleted rows
leaked — confirm the `where deleted is null` filter is present.

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

- The `users` `custom_*` long-tail and the FLDOE HR/charter/certification block
  (`charter_*`, `re_comp_*`, `reading_endorsement_*`, `aca_*`, `w4_*`, etc.) —
  unpivot to the long key/value model in **Batch H**, joined to the
  `custom_fields` metadata crosswalk.
- kipptaf region source + `stg_kippmiami__focus__*` wrappers — deferred to the
  kipptaf-integration plan; add a wrapper only when a mart consumes one of
  these.
- `is_` boolean conversion of Y/N STRING flags and code-value decoding of the
  `INT64` lookups (`gender`, `custom_20120004`) — belongs in an intermediate
  layer if a consumer needs it.

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
6. **Wide-table curation:** `users` carries the curated core + the 13 existing
   FLDOE-mapped `custom_NNN` columns only; the custom long-tail is explicitly
   deferred to Batch H. ✓
7. **Type consistency:** each YAML `data_type` matches the warehouse type pulled
   from `INFORMATION_SCHEMA.COLUMNS` — re-verify during build the `users`
   mixed-type columns (`gender`/`custom_20120004` = int, `custom_200000002` =
   numeric, `last_updated_date` = date vs the `timestamp` date columns).
