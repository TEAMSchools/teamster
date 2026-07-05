# Focus Staging — Test History (Batch I) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add contract-enforced `stg_focus__*` staging models for the five
populated Focus test-history tables (`test_history_tests`,
`test_history_test_types`, `test_history_parts`, `test_history_score_types`,
`test_history_score_ranges`) in the `focus` source-system dbt project.

**Architecture:** One staging model + properties YAML per source table, reading
the BQ-native Focus dlt source already declared in
`src/dbt/focus/models/staging/sources-bigquery.yml`. Light cleaning only:
explicit column projection (drop dlt bookkeeping + audit-quad columns), a
uniqueness + `not_null` test on each table's primary key (`id`), and a
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
  from every model. Keep `created_at` / `updated_at` / `uuid`.
- Staging uniqueness + `not_null` tests MUST set `config: severity: error`
  (project default is `warn`).
- All five tables have `id` (`INT64`) as the primary key, NO soft-delete column
  (`deleted` / `inactive` / `active` / `archived` are all absent), and NO `BOOL`
  columns — so no `where deleted is null` filter and no `is_` boolean conversion
  in this batch. Y/N-style flags (`post_secondary`, `is_default`, `transcript`,
  etc.) stay raw `STRING`; convert in an intermediate layer later if a consumer
  needs it.
- All five tables are narrow (≤25 columns after exclusions), so every
  non-excluded column is kept — no curation / no `custom_*` long-tail here.
- Focus columns are already `snake_case`. `test_history_score_ranges.min` and
  `.max` collide with BigQuery aggregate-function names; bare references happen
  to parse, but the repo SQL-style rule (`src/dbt/CLAUDE.md` → SQL Style) and
  sqlfluff treat them as needing backtick-quoting in SQL plus `quote: true` in
  the YAML — apply both. `test_history_score_ranges.level` is NOT a BigQuery
  reserved word and needs no quoting. `test_history_score_types.min_score*` /
  `max_score*` and `test_history_parts.min_score` are ordinary identifiers — no
  quoting.
- Build/test context is the **kippmiami** project, not `focus` standalone.
- The `data_type` values in each YAML below were pulled verbatim from
  `INFORMATION_SCHEMA.COLUMNS` of `dagster_kippmiami_dlt_focus`. `INT64` →
  `int`, `STRING` → `string`, `NUMERIC` → `numeric`, `TIMESTAMP` → `timestamp`
  (BQ legacy-spelling synonyms; contract matches on type, not spelling).

---

## Setup (once, before Task 1)

- [ ] **Install package deps in the worktree** (fresh worktrees have no
      `dbt_packages/`):

```bash
uv run dbt deps --project-dir src/dbt/kippmiami
```

---

### Task 1: `stg_focus__test_history_tests`

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__test_history_tests.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__test_history_tests.yml`

**Interfaces:**

- Consumes: `source("focus", "test_history_tests")`
- Produces: model `stg_focus__test_history_tests`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    test_type_id,
    district_id,
    fas_test_id,
    min_score_type,
    title,
    short_name,
    score_types,
    test_code,
    test_level,
    post_secondary,
    inter_district,
    allow_profiles_modify,
    allow_profiles_create,
    allow_profiles_view,
    passing_score,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "test_history_tests") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__test_history_tests
    description: >-
      Focus test-history test definitions — one row per test, scoped by
      district. The catalog of assessments tracked in Focus Test History.
    columns:
      - name: id
        description: Primary key — Focus test-history test id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: test_type_id
        description: Foreign key to the Focus test-history test type.
        data_type: int
      - name: district_id
        description: Focus district id the test belongs to.
        data_type: int
      - name: fas_test_id
        description: Florida Assessment System test id mapped to this test.
        data_type: int
      - name: min_score_type
        description: Score-type id used for the minimum / passing score.
        data_type: int
      - name: title
        description: Full test name.
        data_type: string
      - name: short_name
        description: Abbreviated test label.
        data_type: string
      - name: score_types
        description: Encoded list of score-type ids associated with the test.
        data_type: string
      - name: test_code
        description: State or district reporting code for the test.
        data_type: string
      - name: test_level
        description: Grade band or level the test targets.
        data_type: string
      - name: post_secondary
        description: Y/N — whether the test is a post-secondary assessment.
        data_type: string
      - name: inter_district
        description: Y/N — whether the test is shared across districts.
        data_type: string
      - name: allow_profiles_modify
        description: Y/N — whether profile users may modify scores.
        data_type: string
      - name: allow_profiles_create
        description: Y/N — whether profile users may create scores.
        data_type: string
      - name: allow_profiles_view
        description: Y/N — whether profile users may view scores.
        data_type: string
      - name: passing_score
        description: Passing-score threshold or label for the test.
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
`uv run dbt build --select stg_focus__test_history_tests --project-dir src/dbt/kippmiami`
Expected: model builds; `unique` + `not_null` tests on `id` PASS. A contract
mismatch here means a `data_type` in the YAML disagrees with the warehouse — fix
the YAML to match `INFORMATION_SCHEMA.COLUMNS`.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__test_history_tests.sql src/dbt/focus/models/staging/properties/stg_focus__test_history_tests.yml
git commit -m "feat(dbt): add stg_focus__test_history_tests (#4213)"
```

---

### Task 2: `stg_focus__test_history_test_types`

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__test_history_test_types.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__test_history_test_types.yml`

**Interfaces:**

- Consumes: `source("focus", "test_history_test_types")`
- Produces: model `stg_focus__test_history_test_types`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    district_id,
    title,
    sort_order,
    is_default,
    created_at,
    updated_at,
from {{ source("focus", "test_history_test_types") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__test_history_test_types
    description: >-
      Focus test-history test types — one row per test type, scoped by district.
      Lookup that groups tests into categories.
    columns:
      - name: id
        description: Primary key — Focus test-history test type id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: district_id
        description: Focus district id the test type belongs to.
        data_type: int
      - name: title
        description: Full test type name.
        data_type: string
      - name: sort_order
        description: Display sort order within the test type list.
        data_type: int
      - name: is_default
        description: Y/N — whether this is the default test type.
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
`uv run dbt build --select stg_focus__test_history_test_types --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__test_history_test_types.sql src/dbt/focus/models/staging/properties/stg_focus__test_history_test_types.yml
git commit -m "feat(dbt): add stg_focus__test_history_test_types (#4213)"
```

---

### Task 3: `stg_focus__test_history_parts`

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__test_history_parts.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__test_history_parts.yml`

**Interfaces:**

- Consumes: `source("focus", "test_history_parts")`
- Produces: model `stg_focus__test_history_parts`, grain one row per `id` (a
  subtest / part of a test).

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    test_id,
    district_id,
    fas_section_id,
    title,
    short_name,
    subject_code,
    subject,
    sort_order,
    score_types,
    transcript,
    min_scale_score,
    min_score,
    max_syear,
    graph_score,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "test_history_parts") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__test_history_parts
    description: >-
      Focus test-history parts — one row per test part (subtest / section) of a
      test-history test, including subject and score-type mapping.
    columns:
      - name: id
        description: Primary key — Focus test-history part id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: test_id
        description: Foreign key to the parent Focus test-history test.
        data_type: int
      - name: district_id
        description: Focus district id the part belongs to.
        data_type: int
      - name: fas_section_id
        description: Florida Assessment System section id mapped to this part.
        data_type: int
      - name: title
        description: Full test part name.
        data_type: string
      - name: short_name
        description: Abbreviated test part label.
        data_type: string
      - name: subject_code
        description: Subject reporting code for the part.
        data_type: string
      - name: subject
        description: Subject name for the part.
        data_type: string
      - name: sort_order
        description: Display sort order within the part list.
        data_type: numeric
      - name: score_types
        description: Encoded list of score-type ids associated with the part.
        data_type: string
      - name: transcript
        description: Y/N — whether the part appears on the transcript.
        data_type: string
      - name: min_scale_score
        description: Minimum scale score for the part.
        data_type: int
      - name: min_score
        description: Minimum-score threshold or label for the part.
        data_type: string
      - name: max_syear
        description: Latest Focus school year the part is valid for.
        data_type: int
      - name: graph_score
        description: Flag — whether the part's score is graphed.
        data_type: int
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
`uv run dbt build --select stg_focus__test_history_parts --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS. Watch the mixed types on
the score columns — `min_score` is `string` while `min_scale_score` is `int`;
match the YAML `data_type` to the warehouse type exactly, or the contract fails.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__test_history_parts.sql src/dbt/focus/models/staging/properties/stg_focus__test_history_parts.yml
git commit -m "feat(dbt): add stg_focus__test_history_parts (#4213)"
```

---

### Task 4: `stg_focus__test_history_score_types`

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__test_history_score_types.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__test_history_score_types.yml`

**Interfaces:**

- Consumes: `source("focus", "test_history_score_types")`
- Produces: model `stg_focus__test_history_score_types`, grain one row per `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    district_id,
    title,
    short_name,
    data_type,
    summary_type,
    select_options,
    transcript,
    sort_order,
    min_score,
    max_score,
    min_score1,
    max_score1,
    min_score2,
    max_score2,
    min_score3,
    max_score3,
    min_score4,
    max_score4,
    created_at,
    updated_at,
from {{ source("focus", "test_history_score_types") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__test_history_score_types
    description: >-
      Focus test-history score types — one row per score type, scoped by
      district. Defines how a test or part is scored, including up to four
      banded min/max score ranges.
    columns:
      - name: id
        description: Primary key — Focus test-history score type id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: district_id
        description: Focus district id the score type belongs to.
        data_type: int
      - name: title
        description: Full score type name.
        data_type: string
      - name: short_name
        description: Abbreviated score type label.
        data_type: string
      - name: data_type
        description: Underlying data type of the score (e.g. numeric, select).
        data_type: string
      - name: summary_type
        description: How the score type rolls up in summaries.
        data_type: string
      - name: select_options
        description: Encoded select-option values when the score is a picklist.
        data_type: string
      - name: transcript
        description: Y/N — whether the score type appears on the transcript.
        data_type: string
      - name: sort_order
        description: Display sort order within the score type list.
        data_type: numeric
      - name: min_score
        description: Minimum valid score for the primary band.
        data_type: numeric
      - name: max_score
        description: Maximum valid score for the primary band.
        data_type: numeric
      - name: min_score1
        description: Minimum valid score for band 1.
        data_type: numeric
      - name: max_score1
        description: Maximum valid score for band 1.
        data_type: numeric
      - name: min_score2
        description: Minimum valid score for band 2.
        data_type: numeric
      - name: max_score2
        description: Maximum valid score for band 2.
        data_type: numeric
      - name: min_score3
        description: Minimum valid score for band 3.
        data_type: numeric
      - name: max_score3
        description: Maximum valid score for band 3.
        data_type: numeric
      - name: min_score4
        description: Minimum valid score for band 4.
        data_type: numeric
      - name: max_score4
        description: Maximum valid score for band 4.
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
`uv run dbt build --select stg_focus__test_history_score_types --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS. All `min_score*` /
`max_score*` columns are `numeric` (NOT `float64`) — declaring `float64` would
pass parse but fail the contract.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__test_history_score_types.sql src/dbt/focus/models/staging/properties/stg_focus__test_history_score_types.yml
git commit -m "feat(dbt): add stg_focus__test_history_score_types (#4213)"
```

---

### Task 5: `stg_focus__test_history_score_ranges`

`test_history_score_ranges` has the columns `min` and `max`, which collide with
BigQuery aggregate-function names. Per the repo SQL-style rule they are
backtick-quoted in the SQL **and** carry `quote: true` in the YAML. The `level`
column is NOT a BigQuery reserved word and needs no quoting. There is no `uuid`
column on this table — do not add one.

**Files:**

- Create:
  `src/dbt/focus/models/staging/stg_focus__test_history_score_ranges.sql`
- Create:
  `src/dbt/focus/models/staging/properties/stg_focus__test_history_score_ranges.yml`

**Interfaces:**

- Consumes: `source("focus", "test_history_score_ranges")`
- Produces: model `stg_focus__test_history_score_ranges`, grain one row per
  `id`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    id,
    part_id,
    score_type_id,
    legacy,
    title,
    level,
    gradelevel,
    form,
    `min`,
    `max`,
    created_at,
    updated_at,
from {{ source("focus", "test_history_score_ranges") }}
```

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: stg_focus__test_history_score_ranges
    description: >-
      Focus test-history score ranges — one row per score range, mapping a part
      and score type to a min / max band and performance level by grade.
    columns:
      - name: id
        description: Primary key — Focus test-history score range id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: part_id
        description: Foreign key to the Focus test-history part.
        data_type: int
      - name: score_type_id
        description: Foreign key to the Focus test-history score type.
        data_type: int
      - name: legacy
        description: Legacy id carried over from the prior system.
        data_type: int
      - name: title
        description: Full score range name.
        data_type: string
      - name: level
        description: Performance level label for the range.
        data_type: string
      - name: gradelevel
        description: Grade level the range applies to.
        data_type: string
      - name: form
        description: Test form the range applies to.
        data_type: string
      - name: min
        description: Lower bound of the score range.
        data_type: numeric
        quote: true
      - name: max
        description: Upper bound of the score range.
        data_type: numeric
        quote: true
      - name: created_at
        description: Row creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Row last-update timestamp in Focus.
        data_type: timestamp
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select stg_focus__test_history_score_ranges --project-dir src/dbt/kippmiami`
Expected: builds; `unique` + `not_null` on `id` PASS. If it fails with a parse
or contract error on `min` / `max`, confirm the SQL backticks them and the YAML
sets `quote: true` on both.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/models/staging/stg_focus__test_history_score_ranges.sql src/dbt/focus/models/staging/properties/stg_focus__test_history_score_ranges.yml
git commit -m "feat(dbt): add stg_focus__test_history_score_ranges (#4213)"
```

---

## Final verification

- [ ] **Build all five together:**

```bash
uv run dbt build --select stg_focus__test_history_tests stg_focus__test_history_test_types stg_focus__test_history_parts stg_focus__test_history_score_types stg_focus__test_history_score_ranges --project-dir src/dbt/kippmiami
```

Expected: 5 models build, 10 tests (unique + not_null per model) PASS.

- [ ] **Lint the new files** (sqlfluff/yamllint fire at pre-push/CI, not the
      commit hook):

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/focus/models/staging/stg_focus__test_history_tests.sql \
  src/dbt/focus/models/staging/stg_focus__test_history_test_types.sql \
  src/dbt/focus/models/staging/stg_focus__test_history_parts.sql \
  src/dbt/focus/models/staging/stg_focus__test_history_score_types.sql \
  src/dbt/focus/models/staging/stg_focus__test_history_score_ranges.sql \
  src/dbt/focus/models/staging/properties/stg_focus__test_history_tests.yml \
  src/dbt/focus/models/staging/properties/stg_focus__test_history_test_types.yml \
  src/dbt/focus/models/staging/properties/stg_focus__test_history_parts.yml \
  src/dbt/focus/models/staging/properties/stg_focus__test_history_score_types.yml \
  src/dbt/focus/models/staging/properties/stg_focus__test_history_score_ranges.yml
```

(Run from inside the worktree.)

## Out of scope (other plans / issues)

- Intermediate / mart models joining tests → parts → score types → score ranges
  into a usable test-history grain — deferred; this batch lands the raw staging
  layer only.
- kipptaf region source + `stg_kippmiami__focus__*` wrappers — deferred to the
  kipptaf-integration plan; add a wrapper only when a mart consumes one of
  these.
- These five tables carry NO `custom_*` long-tail columns, so the Batch H
  custom-field unpivot does not touch them.

## Self-review checklist (run before handing off)

1. **Spec coverage:** all five test-history tables have a staging task. ✓
2. **Placeholder scan:** every task has complete SQL + complete YAML + exact
   build command. ✓
3. **Type consistency:** each YAML `data_type` matches the warehouse type pulled
   from `INFORMATION_SCHEMA.COLUMNS` (int/string/numeric/timestamp).
   `test_history_score_types` uses `numeric` for all min/max bands;
   `test_history_parts.sort_order` is `numeric` while
   `test_history_test_types.sort_order` is `int` — verified against the schema,
   not assumed uniform. ✓
4. **Audit-quad + dlt exclusion:** none of the five SELECTs project
   `created_by_class` / `created_by_id` / `updated_by_class` / `updated_by_id`
   or any `_dlt_*` column. ✓
5. **PK + reserved words:** all five use `id` for the uniqueness + `not_null` PK
   test; `test_history_score_ranges.min` / `.max` are backtick- quoted in SQL
   with `quote: true` in YAML; `level` is left unquoted (not reserved);
   `test_history_score_ranges` has no `uuid`. ✓
