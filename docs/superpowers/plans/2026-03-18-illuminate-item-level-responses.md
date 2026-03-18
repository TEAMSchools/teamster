# Illuminate Item-Level Student Responses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest four new Illuminate `dna_assessments` tables via DLT and build
a staging + intermediate dbt layer exposing item-level student response data
(one row per student × question × assessment attempt).

**Architecture:** New DLT assets are registered in `illuminate.yaml`
(auto-generates Dagster assets — no Python changes needed) and wired into the
existing hourly/daily schedules. Four thin staging models pass data through; the
intermediate joins them into the analysis-ready grain. Reporting extract is
explicitly deferred.

**Tech Stack:** DLT (Postgres → BigQuery), dbt (BigQuery dialect), Dagster
(orchestration). Read `src/dbt/CLAUDE.md` and `src/teamster/CLAUDE.md` before
making changes.

---

## File Map

| Action | File                                                                                                                           |
| ------ | ------------------------------------------------------------------------------------------------------------------------------ |
| Modify | `src/teamster/code_locations/kipptaf/dlt/illuminate/config/illuminate.yaml`                                                    |
| Modify | `src/teamster/code_locations/kipptaf/dlt/illuminate/schedules.py`                                                              |
| Modify | `src/dbt/kipptaf/models/illuminate/dlt/sources-illuminate.yml`                                                                 |
| Create | `src/dbt/kipptaf/models/illuminate/dlt/staging/stg_illuminate__dna_assessments__students_assessments_responses.sql`            |
| Create | `src/dbt/kipptaf/models/illuminate/dlt/staging/properties/stg_illuminate__dna_assessments__students_assessments_responses.yml` |
| Create | `src/dbt/kipptaf/models/illuminate/dlt/staging/stg_illuminate__dna_assessments__responses.sql`                                 |
| Create | `src/dbt/kipptaf/models/illuminate/dlt/staging/properties/stg_illuminate__dna_assessments__responses.yml`                      |
| Create | `src/dbt/kipptaf/models/illuminate/dlt/staging/stg_illuminate__dna_assessments__field_responses.sql`                           |
| Create | `src/dbt/kipptaf/models/illuminate/dlt/staging/properties/stg_illuminate__dna_assessments__field_responses.yml`                |
| Create | `src/dbt/kipptaf/models/illuminate/dlt/staging/stg_illuminate__dna_assessments__fields.sql`                                    |
| Create | `src/dbt/kipptaf/models/illuminate/dlt/staging/properties/stg_illuminate__dna_assessments__fields.yml`                         |
| Create | `src/dbt/kipptaf/models/illuminate/dlt/intermediate/int_illuminate__student_item_responses.sql`                                |
| Create | `src/dbt/kipptaf/models/illuminate/dlt/intermediate/properties/int_illuminate__student_item_responses.yml`                     |

---

### Task 1: DLT ingestion config — add 4 tables

**Files:**

- Modify:
  `src/teamster/code_locations/kipptaf/dlt/illuminate/config/illuminate.yaml`

- [ ] **Step 1: Add 4 entries to the `dna_assessments` tables list**

Insert into `illuminate.yaml` under `schema: dna_assessments`, maintaining
alphabetical order (between `assessments_reporting_groups` and
`performance_band_sets`):

```yaml
- table_name: field_responses
- table_name: fields
```

And after `reporting_groups`, before `students_assessments`:

```yaml
- table_name: responses
```

And after `students_assessments`:

```yaml
- table_name: students_assessments_responses
  op_tags:
    dagster/priority: "1"
    dagster-k8s/config:
      container_config:
        resources:
          requests:
            cpu: 500m
          limits:
            cpu: 1000m
```

The final `dna_assessments` tables list should be:

```yaml
- schema: dna_assessments
  tables:
    - table_name: agg_student_responses
      filter_date_taken: true
      op_tags:
        dagster/priority: "1"
    - table_name: agg_student_responses_group
      op_tags:
        dagster/priority: "1"
        dagster-k8s/config:
          container_config:
            resources:
              requests:
                cpu: 500m
              limits:
                cpu: 1000m
    - table_name: agg_student_responses_standard
      op_tags:
        dagster/priority: "1"
        dagster-k8s/config:
          container_config:
            resources:
              requests:
                cpu: 500m
              limits:
                cpu: 1000m
    - table_name: assessment_grade_levels
    - table_name: assessment_standards
    - table_name: assessments
    - table_name: assessments_reporting_groups
    - table_name: field_responses
    - table_name: fields
    - table_name: performance_band_sets
    - table_name: performance_bands
    - table_name: reporting_groups
    - table_name: responses
    - table_name: students_assessments
      filter_date_taken: true
      op_tags:
        dagster/priority: "1"
    - table_name: students_assessments_responses
      op_tags:
        dagster/priority: "1"
        dagster-k8s/config:
          container_config:
            resources:
              requests:
                cpu: 500m
              limits:
                cpu: 1000m
```

- [ ] **Step 2: Verify yaml parses**

```bash
uv run python -c "import yaml, pathlib; print(yaml.safe_load(pathlib.Path('src/teamster/code_locations/kipptaf/dlt/illuminate/config/illuminate.yaml').read_text())['assets'][1]['tables'])"
```

Expected: list containing the new entries including `field_responses`, `fields`,
`responses`, `students_assessments_responses`.

---

### Task 2: Dagster schedules — wire new tables

**Files:**

- Modify: `src/teamster/code_locations/kipptaf/dlt/illuminate/schedules.py`

- [ ] **Step 1: Add `students_assessments_responses` to the hourly schedule**

In `illuminate_dlt_hourly_asset_job_schedule`, add after `students_assessments`:

```python
        f"{asset_key_prefix}/dna_assessments/students_assessments_responses",
```

- [ ] **Step 2: Add `responses`, `field_responses`, `fields` to the daily
      schedule**

In `illuminate_dlt_daily_asset_job_schedule`, add (in alphabetical order within
`dna_assessments`):

```python
        f"{asset_key_prefix}/dna_assessments/field_responses",
        f"{asset_key_prefix}/dna_assessments/fields",
```

after `f"{asset_key_prefix}/dna_assessments/reporting_groups"`, and:

```python
        f"{asset_key_prefix}/dna_assessments/responses",
```

after `f"{asset_key_prefix}/dna_assessments/reporting_groups"` (maintaining
alphabetical order: `field_responses`, `fields`, `performance_band_sets`,
`performance_bands`, `reporting_groups`, `responses`).

The `dna_assessments` lines in `illuminate_dlt_daily_asset_job_schedule` should
be:

```python
        f"{asset_key_prefix}/dna_assessments/field_responses",
        f"{asset_key_prefix}/dna_assessments/fields",
        f"{asset_key_prefix}/dna_assessments/performance_band_sets",
        f"{asset_key_prefix}/dna_assessments/performance_bands",
        f"{asset_key_prefix}/dna_assessments/reporting_groups",
        f"{asset_key_prefix}/dna_assessments/responses",
```

- [ ] **Step 3: Validate Dagster definitions**

```bash
uv run dagster definitions validate -m teamster.code_locations.kipptaf.definitions
```

Expected: `Definitions loaded successfully.` (or equivalent success message). If
it fails, check the YAML indentation and asset key strings.

- [ ] **Step 4: Commit**

```bash
git add src/teamster/code_locations/kipptaf/dlt/illuminate/config/illuminate.yaml
git add src/teamster/code_locations/kipptaf/dlt/illuminate/schedules.py
git commit -m "feat(illuminate): add DLT ingestion for item-level response tables"
```

---

### Task 3: dbt source registration

**Files:**

- Modify: `src/dbt/kipptaf/models/illuminate/dlt/sources-illuminate.yml`

The `illuminate_dna_assessments` source already exists in this file. Four new
table entries are needed under it. Each entry follows the exact same pattern as
the existing entries — `name`, then `config.meta.dagster.group` and
`config.meta.dagster.asset_key`.

- [ ] **Step 1: Add 4 source entries to `illuminate_dna_assessments`**

After the `students_assessments` entry (end of the `illuminate_dna_assessments`
block), add:

```yaml
- name: field_responses
  config:
    meta:
      dagster:
        group: illuminate
        asset_key:
          - kipptaf
          - dlt
          - illuminate
          - dna_assessments
          - field_responses
- name: fields
  config:
    meta:
      dagster:
        group: illuminate
        asset_key:
          - kipptaf
          - dlt
          - illuminate
          - dna_assessments
          - fields
- name: responses
  config:
    meta:
      dagster:
        group: illuminate
        asset_key:
          - kipptaf
          - dlt
          - illuminate
          - dna_assessments
          - responses
- name: students_assessments_responses
  config:
    meta:
      dagster:
        group: illuminate
        asset_key:
          - kipptaf
          - dlt
          - illuminate
          - dna_assessments
          - students_assessments_responses
```

- [ ] **Step 2: Commit**

```bash
git add src/dbt/kipptaf/models/illuminate/dlt/sources-illuminate.yml
git commit -m "feat(illuminate): register item-level response source tables in dbt"
```

---

### Task 4: Staging model — `students_assessments_responses`

**Files:**

- Create:
  `src/dbt/kipptaf/models/illuminate/dlt/staging/stg_illuminate__dna_assessments__students_assessments_responses.sql`
- Create:
  `src/dbt/kipptaf/models/illuminate/dlt/staging/properties/stg_illuminate__dna_assessments__students_assessments_responses.yml`

`materialized: table` and `contract: enforced: true` are inherited from
`dbt_project.yml` directory defaults — do not add them to the properties YAML.

- [ ] **Step 1: Write the properties YAML (defines the contract and tests)**

```yaml
models:
  - name: stg_illuminate__dna_assessments__students_assessments_responses
    columns:
      - name: student_assessment_response_id
        data_type: int64
        data_tests:
          - unique:
              config:
                store_failures: true
      - name: assessment_id
        data_type: int64
      - name: student_assessment_id
        data_type: int64
      - name: field_id
        data_type: int64
      - name: response_id
        data_type: int64
      - name: version_id
        data_type: int64
      - name: manual_score
        data_type: boolean
```

- [ ] **Step 2: Write the SQL model**

```sql
select
    *,
from {{ source("illuminate_dna_assessments", "students_assessments_responses") }}
```

- [ ] **Step 3: Compile to verify syntax**

Using the dbt MCP tool: compile with
`--select stg_illuminate__dna_assessments__students_assessments_responses`

Or via CLI from `src/dbt/kipptaf/`:

```bash
uv run dbt compile --select stg_illuminate__dna_assessments__students_assessments_responses
```

Expected: compiled SQL appears in `target/compiled/`. If the source table
doesn't exist yet (DLT hasn't run), compilation may warn about missing relations
— this is expected at this stage.

---

### Task 5: Staging model — `responses`

**Files:**

- Create:
  `src/dbt/kipptaf/models/illuminate/dlt/staging/stg_illuminate__dna_assessments__responses.sql`
- Create:
  `src/dbt/kipptaf/models/illuminate/dlt/staging/properties/stg_illuminate__dna_assessments__responses.yml`

- [ ] **Step 1: Write the properties YAML**

```yaml
models:
  - name: stg_illuminate__dna_assessments__responses
    columns:
      - name: response_id
        data_type: int64
        data_tests:
          - unique:
              config:
                store_failures: true
      - name: response
        data_type: string
```

- [ ] **Step 2: Write the SQL model**

```sql
select
    *,
from {{ source("illuminate_dna_assessments", "responses") }}
```

- [ ] **Step 3: Compile to verify syntax**

```bash
uv run dbt compile --select stg_illuminate__dna_assessments__responses
```

---

### Task 6: Staging model — `field_responses`

**Files:**

- Create:
  `src/dbt/kipptaf/models/illuminate/dlt/staging/stg_illuminate__dna_assessments__field_responses.sql`
- Create:
  `src/dbt/kipptaf/models/illuminate/dlt/staging/properties/stg_illuminate__dna_assessments__field_responses.yml`

- [ ] **Step 1: Write the properties YAML**

The uniqueness key for this table is the composite
`(field_id, response_id, version_id)` — no single column is unique.

```yaml
models:
  - name: stg_illuminate__dna_assessments__field_responses
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - field_id
              - response_id
              - version_id
          config:
            store_failures: true
    columns:
      - name: field_response_id
        data_type: int64
      - name: field_id
        data_type: int64
      - name: response_id
        data_type: int64
      - name: points
        data_type: numeric
      - name: choice
        data_type: string
      - name: rationale
        data_type: string
      - name: version_id
        data_type: int64
```

- [ ] **Step 2: Write the SQL model**

```sql
select
    *,
from {{ source("illuminate_dna_assessments", "field_responses") }}
```

- [ ] **Step 3: Compile to verify syntax**

```bash
uv run dbt compile --select stg_illuminate__dna_assessments__field_responses
```

---

### Task 7: Staging model — `fields`

**Files:**

- Create:
  `src/dbt/kipptaf/models/illuminate/dlt/staging/stg_illuminate__dna_assessments__fields.sql`
- Create:
  `src/dbt/kipptaf/models/illuminate/dlt/staging/properties/stg_illuminate__dna_assessments__fields.yml`

**Key notes:**

- This is the only new staging model that is NOT a pure pass-through — it
  filters soft-deleted items (`WHERE deleted_at IS NULL`), consistent with
  `stg_illuminate__dna_assessments__assessments` and
  `stg_illuminate__dna_repositories__repository_fields`.
- The `fields` table contains two Postgres array-typed columns (`sort_order` as
  `_int4`, `sheet_responses` as `_varchar`) that DLT ingests as BigQuery
  REPEATED fields. These are not used in the intermediate model but pass through
  the staging layer unchanged.
- The column `order` is a SQL reserved word — reference it as `` `order` `` in
  SQL. It is aliased to `field_order` in the intermediate model (not here).
- The complete column list below is based on SchemaSpy documentation. **After
  DLT runs for the first time, verify the complete column list by querying
  `INFORMATION_SCHEMA.COLUMNS` (see Step 4) and update this YAML if there are
  discrepancies.**

- [ ] **Step 1: Write the properties YAML**

```yaml
models:
  - name: stg_illuminate__dna_assessments__fields
    columns:
      - name: field_id
        data_type: int64
        data_tests:
          - unique:
              config:
                store_failures: true
      - name: version_id
        data_type: int64
      - name: field_type_id
        data_type: int64
      - name: order
        data_type: int64
      - name: body
        data_type: string
      - name: deleted_at
        data_type: timestamp
      - name: created_at
        data_type: timestamp
      - name: updated_at
        data_type: timestamp
      - name: sort_order
        data_type: array<int64>
      - name: sheet_responses
        data_type: array<string>
```

> **Note:** After DLT ingests `fields` for the first time, run the query below
> to verify all columns are accounted for and add any that are missing:
>
> ```sql
> select column_name, data_type
> from `teamster-332318`.dagster_kipptaf_dlt_illuminate_dna_assessments.INFORMATION_SCHEMA.COLUMNS
> where table_name = 'fields'
> order by ordinal_position
> ```

- [ ] **Step 2: Write the SQL model**

```sql
select
    *,
from {{ source("illuminate_dna_assessments", "fields") }}
where deleted_at is null
```

- [ ] **Step 3: Compile to verify syntax**

```bash
uv run dbt compile --select stg_illuminate__dna_assessments__fields
```

- [ ] **Step 4: Commit all four staging models**

```bash
git add src/dbt/kipptaf/models/illuminate/dlt/staging/stg_illuminate__dna_assessments__students_assessments_responses.sql
git add src/dbt/kipptaf/models/illuminate/dlt/staging/properties/stg_illuminate__dna_assessments__students_assessments_responses.yml
git add src/dbt/kipptaf/models/illuminate/dlt/staging/stg_illuminate__dna_assessments__responses.sql
git add src/dbt/kipptaf/models/illuminate/dlt/staging/properties/stg_illuminate__dna_assessments__responses.yml
git add src/dbt/kipptaf/models/illuminate/dlt/staging/stg_illuminate__dna_assessments__field_responses.sql
git add src/dbt/kipptaf/models/illuminate/dlt/staging/properties/stg_illuminate__dna_assessments__field_responses.yml
git add src/dbt/kipptaf/models/illuminate/dlt/staging/stg_illuminate__dna_assessments__fields.sql
git add src/dbt/kipptaf/models/illuminate/dlt/staging/properties/stg_illuminate__dna_assessments__fields.yml
git commit -m "feat(illuminate): add staging models for item-level response tables"
```

---

### Task 8: Intermediate model — `int_illuminate__student_item_responses`

**Files:**

- Create:
  `src/dbt/kipptaf/models/illuminate/dlt/intermediate/int_illuminate__student_item_responses.sql`
- Create:
  `src/dbt/kipptaf/models/illuminate/dlt/intermediate/properties/int_illuminate__student_item_responses.yml`

**Key notes:**

- Materialized as **view** — the `dlt/intermediate/` directory has no
  `materialized` override in `dbt_project.yml`; the global default (view)
  applies. Do not add a `+materialized` config.
- All joins are INNER — all FK columns in `students_assessments_responses` are
  NOT NULL per the Illuminate schema.
- `fields.order` is a SQL reserved word — reference it as `` f.`order` `` and
  alias to `field_order`.
- Soft-deleted fields are already excluded upstream by
  `stg_illuminate__dna_assessments__fields`. No `deleted_at` filter is needed in
  this model.
- `field_responses.choice` is deliberately excluded — its equivalence to
  `responses.response` needs validation against actual ingested data before
  including it.

- [ ] **Step 1: Write the properties YAML**

```yaml
models:
  - name: int_illuminate__student_item_responses
    columns:
      - name: student_assessment_response_id
        data_type: int64
        data_tests:
          - unique:
              config:
                store_failures: true
      - name: student_assessment_id
        data_type: int64
      - name: assessment_id
        data_type: int64
      - name: version_id
        data_type: int64
      - name: field_id
        data_type: int64
      - name: field_order
        data_type: int64
      - name: response_id
        data_type: int64
      - name: response
        data_type: string
      - name: is_correct
        data_type: boolean
      - name: points
        data_type: numeric
      - name: manual_score
        data_type: boolean
```

- [ ] **Step 2: Write the SQL model**

```sql
select
    sar.student_assessment_response_id,
    sar.student_assessment_id,
    sar.assessment_id,
    sar.version_id,
    sar.field_id,

    f.`order` as field_order,

    sar.response_id,
    r.response,

    fr.points > 0 as is_correct,
    fr.points,
    sar.manual_score,
from {{ ref("stg_illuminate__dna_assessments__students_assessments_responses") }} as sar
inner join
    {{ ref("stg_illuminate__dna_assessments__responses") }} as r
    on sar.response_id = r.response_id
inner join
    {{ ref("stg_illuminate__dna_assessments__field_responses") }} as fr
    on sar.field_id = fr.field_id
    and sar.response_id = fr.response_id
    and sar.version_id = fr.version_id
inner join
    {{ ref("stg_illuminate__dna_assessments__fields") }} as f
    on sar.field_id = f.field_id
```

- [ ] **Step 3: Compile to verify syntax**

```bash
uv run dbt compile --select int_illuminate__student_item_responses
```

Expected: compiled SQL in `target/compiled/`. Verify the JOIN structure and
column aliases look correct in the compiled output.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/illuminate/dlt/intermediate/int_illuminate__student_item_responses.sql
git add src/dbt/kipptaf/models/illuminate/dlt/intermediate/properties/int_illuminate__student_item_responses.yml
git commit -m "feat(illuminate): add int_illuminate__student_item_responses intermediate model"
```

---

### Task 9: Post-ingestion verification (after DLT runs in production)

This task cannot be completed until the DLT assets have run and populated the
BigQuery tables. Run it after the first successful DLT execution.

**Files:**

- Possibly modify:
  `src/dbt/kipptaf/models/illuminate/dlt/staging/properties/stg_illuminate__dna_assessments__fields.yml`

- [ ] **Step 1: Verify `fields` column list is complete**

```sql
select column_name, data_type
from `teamster-332318`.dagster_kipptaf_dlt_illuminate_dna_assessments.INFORMATION_SCHEMA.COLUMNS
where table_name = 'fields'
order by ordinal_position
```

Compare output against the columns listed in
`stg_illuminate__dna_assessments__fields.yml`. Add any missing columns. Remove
any that don't exist in the actual table.

- [ ] **Step 2: Verify `field_responses.choice` vs `responses.response`**

```sql
select
    r.response,
    fr.choice,
    count(*) as n,
from `teamster-332318`.dagster_kipptaf_dlt_illuminate_dna_assessments.field_responses as fr
inner join `teamster-332318`.dagster_kipptaf_dlt_illuminate_dna_assessments.responses as r
    on fr.response_id = r.response_id
group by r.response, fr.choice
order by n desc
limit 50
```

If `choice` and `response` are identical for all combinations, `choice` is
redundant and can remain excluded. If they differ, document what `choice`
represents and decide whether to add it to the intermediate model (requires a
spec update before doing so).

- [ ] **Step 3: Run dbt tests**

```bash
uv run dbt test --select stg_illuminate__dna_assessments__students_assessments_responses stg_illuminate__dna_assessments__responses stg_illuminate__dna_assessments__field_responses stg_illuminate__dna_assessments__fields int_illuminate__student_item_responses
```

All uniqueness tests should pass. If any fail, investigate the source data — do
not weaken the tests.

- [ ] **Step 4: Commit any YAML corrections**

```bash
git add src/dbt/kipptaf/models/illuminate/dlt/staging/properties/stg_illuminate__dna_assessments__fields.yml
git commit -m "fix(illuminate): correct fields staging YAML after first DLT ingestion"
```

(Skip this step if no corrections were needed.)
