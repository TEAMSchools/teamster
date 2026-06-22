# Focus Staging — Discipline Lookups (Batch F) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add contract-enforced `stg_focus__*` staging models for the two
populated Focus discipline-lookup tables (`referral_actions`, `referral_codes`)
in the `focus` source-system dbt project.

**Architecture:** One staging model + properties YAML per source table, reading
the BQ-native Focus dlt source already declared in
`src/dbt/focus/models/staging/sources-bigquery.yml`. Light cleaning only:
explicit column projection (drop dlt bookkeeping + audit-quad columns), a
uniqueness + `not_null` test on each table's `id` primary key, and a
`description:` on the model and every column. Models build inside the consuming
district project (`kippmiami`), which sets `focus_schema` and imports the
`focus` package.

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
  from every model. Keep `created_at` / `updated_at`. Neither table in this
  batch has a `uuid` column.
- Staging uniqueness + `not_null` tests MUST set `config: severity: error`
  (project default is `warn`). PK is `id` on both tables.
- Neither table has a `deleted` (soft-delete) column, so no
  `where deleted is null` filter in this batch. Neither has a `BOOL` column; the
  many Focus `INT64` flag columns (0/1) and `STRING` Y/N flags stay raw (convert
  in an intermediate layer later if a consumer needs typed booleans).
- Both tables are narrow (<=40 non-excluded columns), so all non-excluded
  columns are kept — no curation. The wide-table `custom_*` long-tail rule does
  not apply here (neither table has `custom_*` columns).
- Focus columns are already `snake_case`; no BigQuery-reserved-word columns in
  either table, so no backtick-quoting / `quote: true`. (`type` and `code` are
  not reserved words in BigQuery; `severity` / `priority` likewise.)
- Build/test context is the **kippmiami** project, not `focus` standalone.
- `referral_actions.priority` does NOT exist; `referral_codes.priority` is
  `NUMERIC` — declare it `numeric` (NOT `float64`; they are distinct BQ types
  and `float64` fails contract enforcement).

---

## Setup (once, before Task 1)

- [ ] **Install package deps in the worktree** (fresh worktrees have no
      `dbt_packages/`):

```bash
uv run dbt deps --project-dir src/dbt/kippmiami
```

---

### Task 1: `stg_focus__referral_actions`

`referral_actions` defines the disciplinary actions (e.g. suspension types) that
can result from a referral, with day-limit thresholds and grade-level bounds. 35
source columns; the audit-quad (`created_by_class`, `created_by_id`,
`updated_by_class`, `updated_by_id`) and `_dlt_*` are excluded, leaving 31
projected columns.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__referral_actions.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__referral_actions.yml`

**Interfaces:**

- Consumes: `source("focus", "referral_actions")`
- Produces: model `stg_focus__referral_actions`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    title,
    local_code,
    state_code,
    severity,
    profiles_edit,
    min_days_referral,
    max_days_referral,
    max_days_year,
    max_days_ese,
    max_days_504,
    warning_level,
    min_grade_level,
    max_grade_level,
    withdraw_code,
    restrict_reentry,
    school_exemptions,
    max_referral_days_ese,
    max_referral_days_504,
    override_profile,
    warning_message,
    start_year,
    end_year,
    detention,
    district_id,
    letter_id,
    letter_source,
    grade_levels,
    type,
    created_at,
    updated_at,
from {{ source("focus", "referral_actions") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__referral_actions
    description: >-
      Focus referral actions — one row per disciplinary action that can result
      from a referral, with day-limit thresholds, grade-level bounds, and the
      letter/profile configuration governing the action.
    columns:
      - name: id
        description: Primary key — Focus referral action id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: title
        description: Full referral action name.
        data_type: string
      - name: local_code
        description: District-local code for the action.
        data_type: string
      - name: state_code
        description: State-reporting code mapped to this action.
        data_type: string
      - name: severity
        description: Severity ranking for the action.
        data_type: int
      - name: profiles_edit
        description: User profiles permitted to edit this action.
        data_type: string
      - name: min_days_referral
        description: Minimum days assignable per referral for this action.
        data_type: int
      - name: max_days_referral
        description: Maximum days assignable per referral for this action.
        data_type: int
      - name: max_days_year
        description: Maximum cumulative days per year for this action.
        data_type: int
      - name: max_days_ese
        description: Maximum days for ESE (special education) students.
        data_type: int
      - name: max_days_504
        description: Maximum days for students on a 504 plan.
        data_type: int
      - name: warning_level
        description: Warning level associated with the action.
        data_type: int
      - name: min_grade_level
        description: Minimum grade level the action applies to.
        data_type: int
      - name: max_grade_level
        description: Maximum grade level the action applies to.
        data_type: int
      - name: withdraw_code
        description:
          Withdrawal code applied when the action withdraws a student.
        data_type: int
      - name: restrict_reentry
        description: Flag (0/1) — whether the action restricts re-entry.
        data_type: int
      - name: school_exemptions
        description: School ids exempted from this action.
        data_type: string
      - name: max_referral_days_ese
        description: Maximum referral days for ESE students.
        data_type: int
      - name: max_referral_days_504
        description: Maximum referral days for students on a 504 plan.
        data_type: int
      - name: override_profile
        description: Profile permitted to override the action limits.
        data_type: string
      - name: warning_message
        description: Warning message shown when the action is applied.
        data_type: string
      - name: start_year
        description: First school year (start year) the action is active.
        data_type: int
      - name: end_year
        description: Last school year (start year) the action is active.
        data_type: int
      - name: detention
        description: Y/N — whether the action is a detention.
        data_type: string
      - name: district_id
        description: Focus district id.
        data_type: int
      - name: letter_id
        description: Letter template id associated with the action.
        data_type: int
      - name: letter_source
        description: Source of the associated letter template.
        data_type: string
      - name: grade_levels
        description: Grade levels the action applies to.
        data_type: string
      - name: type
        description: Referral action type classification.
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
`uv run dbt build --select stg_focus__referral_actions --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` tests on `id` PASS. A contract
mismatch here means a `data_type` in the YAML disagrees with the warehouse — fix
the YAML to match `INFORMATION_SCHEMA.COLUMNS` (all flag/id/year/day columns are
`int`; `title` / codes / messages / `type` / `detention` are `string`).

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__referral_actions.sql src/dbt/focus/models/staging/properties/stg_focus__referral_actions.yml
git commit -m "feat(dbt): add stg_focus__referral_actions (#4213)"
```

---

### Task 2: `stg_focus__referral_codes`

`referral_codes` defines the referral reason codes (incident types) with their
ISS/OSS day ranges and the actions/profiles they map to. 33 source columns; the
audit-quad and `_dlt_*` are excluded, leaving 29 projected columns.

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__referral_codes.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__referral_codes.yml`

**Interfaces:**

- Consumes: `source("focus", "referral_codes")`
- Produces: model `stg_focus__referral_codes`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    title,
    code,
    state_value,
    sesir,
    max_iss,
    min_iss,
    max_oss,
    min_oss,
    actions,
    profiles,
    restrict_reentry,
    severity,
    override_profile,
    warning_message,
    end_year,
    incident_type,
    start_year,
    mobile_app,
    district_id,
    letter_id,
    require_hope,
    require_threat,
    letter_source,
    grade_levels,
    probation_option_ids,
    priority,
    created_at,
    updated_at,
from {{ source("focus", "referral_codes") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__referral_codes
    description: >-
      Focus referral codes — one row per referral reason code (incident type),
      with its ISS/OSS day ranges, SESIR mapping, and the actions and profiles
      the code is associated with.
    columns:
      - name: id
        description: Primary key — Focus referral code id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: title
        description: Full referral code name.
        data_type: string
      - name: code
        description: Short referral code value.
        data_type: string
      - name: state_value
        description: State-reporting value mapped to this code.
        data_type: string
      - name: sesir
        description: SESIR (state incident reporting) code id.
        data_type: int
      - name: max_iss
        description: Maximum in-school-suspension days for this code.
        data_type: int
      - name: min_iss
        description: Minimum in-school-suspension days for this code.
        data_type: int
      - name: max_oss
        description: Maximum out-of-school-suspension days for this code.
        data_type: int
      - name: min_oss
        description: Minimum out-of-school-suspension days for this code.
        data_type: int
      - name: actions
        description: Referral action ids associated with this code.
        data_type: string
      - name: profiles
        description: User profiles permitted to use this code.
        data_type: string
      - name: restrict_reentry
        description: Flag (0/1) — whether the code restricts re-entry.
        data_type: int
      - name: severity
        description: Severity ranking for the code.
        data_type: int
      - name: override_profile
        description: Profile permitted to override the code limits.
        data_type: string
      - name: warning_message
        description: Warning message shown when the code is applied.
        data_type: string
      - name: end_year
        description: Last school year (start year) the code is active.
        data_type: int
      - name: incident_type
        description: Incident type classification for the code.
        data_type: string
      - name: start_year
        description: First school year (start year) the code is active.
        data_type: int
      - name: mobile_app
        description:
          Flag (0/1) — whether the code is available in the mobile app.
        data_type: int
      - name: district_id
        description: Focus district id.
        data_type: int
      - name: letter_id
        description: Letter template id associated with the code.
        data_type: int
      - name: require_hope
        description: Flag (0/1) — whether a HOPE entry is required for the code.
        data_type: int
      - name: require_threat
        description: Flag (0/1) — whether a threat assessment is required.
        data_type: int
      - name: letter_source
        description: Source of the associated letter template.
        data_type: string
      - name: grade_levels
        description: Grade levels the code applies to.
        data_type: string
      - name: probation_option_ids
        description: Probation option ids associated with the code.
        data_type: string
      - name: priority
        description: Display/processing priority for the code.
        data_type: numeric
      - name: created_at
        description: Row creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Row last-update timestamp in Focus.
        data_type: timestamp
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__referral_codes --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS. Note `priority` is
`numeric` (not `int`, not `float64`) — match it exactly or the contract fails.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__referral_codes.sql src/dbt/focus/models/staging/properties/stg_focus__referral_codes.yml
git commit -m "feat(dbt): add stg_focus__referral_codes (#4213)"
```

---

## Final verification

- [ ] **Build both models together:**

```bash
uv run dbt build --select stg_focus__referral_actions stg_focus__referral_codes --project-dir src/dbt/kippmiami
```

Expected: 2 models build, 4 tests (unique + not_null per model) PASS.

- [ ] **Lint the new files** (sqlfluff/yamllint fire at pre-push/CI, not the
      commit hook):

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/focus/models/staging/stg_focus__referral_actions.sql \
  src/dbt/focus/models/staging/stg_focus__referral_codes.sql \
  src/dbt/focus/models/staging/properties/stg_focus__referral_actions.yml \
  src/dbt/focus/models/staging/properties/stg_focus__referral_codes.yml
```

(Run from inside the worktree.)

## Out of scope (other plans / issues)

- The `discipline_*` domain tables (incident-level records) are empty in the
  source and out of scope here — #4220.
- kipptaf region source + `stg_kippmiami__focus__*` wrappers — deferred to the
  kipptaf-integration plan; add a wrapper only when a mart consumes one of
  these.
- Typed boolean conversion of the `INT64` 0/1 flags and `STRING` Y/N flags —
  belongs in an intermediate layer if a consumer needs it.

## Self-review checklist (run before handing off)

1. **Spec coverage:** both populated discipline-lookup tables
   (`referral_actions`, `referral_codes`) have a staging task. ✓
2. **Placeholder scan:** every task has complete SQL + complete YAML + exact
   build command. No TBD/TODO/"add error handling" placeholders. ✓
3. **Type consistency:** each YAML `data_type` matches the warehouse type pulled
   from `INFORMATION_SCHEMA.COLUMNS`. Both PKs are `id` (`int`). Every projected
   column appears in both the SQL `select` and the YAML `columns:` with no
   mismatch. `referral_codes.priority` is `numeric`; all other non-string
   non-timestamp columns are `int`. ✓
4. **Exclusions:** audit-quad (`created_by_class` / `created_by_id` /
   `updated_by_class` / `updated_by_id`) and `_dlt_*` dropped from both;
   `created_at` / `updated_at` retained; neither table has `uuid` or `deleted`.
   ✓
5. **Tests:** `unique` + `not_null` on `id`, both at `config: severity: error`,
   with the per-column tests sorted to the top of `columns:`. ✓
