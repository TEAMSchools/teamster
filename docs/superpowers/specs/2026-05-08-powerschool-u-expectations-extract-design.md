# PowerSchool `U_EXPECTATIONS` Extract — Design

Issue:
[TEAMSchools/teamster#3756](https://github.com/TEAMSchools/teamster/issues/3756)

## Goal

Stand up a recurring BigQuery extract of the `U_EXPECTATIONS` PowerSchool
extension table from Newark production, plus a dbt staging model in
`kippnewark`, so downstream Gradebook Audit work has a queryable source.

The same pattern will be repeated for `U_FLAGS` and `U_EXCEPTIONS` in later
phases. This spec covers `U_EXPECTATIONS` only.

## Decisions

- **Ingest path**: Oracle ODBC via the existing
  `build_powerschool_table_asset()` factory. Reuses the SSH tunnel, retry
  wrapper, Avro serialization, and BigQuery loader already in production.
- **Scope**: `kippnewark` code location only. The Gradebook Audit plugin is
  installed on Newark prod (and a Newark test instance); other districts add the
  same single YAML line when their plugin lands.
- **Partitioning**: `partition_column: whenmodified` — standard for PS extension
  tables, matching the existing `# whenmodified` group in `assets-full.yaml`.
- **Column projection**: pull all columns (no `select_columns`). The standard PS
  audit cols (`dcid`, `whencreated`, `whenmodified`, …) come along for free and
  are needed for the partition filter and grain.
- **Staging grain**: `dcid` (PS extension-table PK). `id`, `school_level`,
  `quarter`, `week_number` are payload columns, not the unique key.
- **Verification**: locally and in branch deployment; no pre-merge Oracle probe
  required.

## Change set

### 1. Dagster YAML

Append to
`src/teamster/code_locations/kippnewark/powerschool/config/assets-full.yaml`
under the `# whenmodified` block:

```yaml
- asset_name: u_expectations
  partition_column: whenmodified
```

No code changes. The asset is auto-included in:

- `powerschool_table_assets_full` (assembled by `assets.py`'s
  `config_from_files` list comprehension)
- the staleness sensor that drives PS materializations
- the standard fiscal-year partitions (`FiscalYearPartitionsDefinition`, start
  `2016-07-01`, July fiscal start, America/New_York)
- the standard GCS landing path:
  `gs://teamster-kippnewark/dagster/kippnewark/powerschool/u_expectations/...avro`
- the standard BigQuery raw load into the `kippnewark_powerschool` dataset

### 2. dbt source entry

Add a new entry in
`src/dbt/powerschool/models/sis/staging/odbc/sources-external.yml` under the
`powerschool_odbc` source, mirroring the existing
`src_powerschool__u_studentsuserfields` block:

```yaml
- name: src_powerschool__u_expectations
  config:
    meta:
      dagster:
        asset_key:
          - "{{ project_name }}"
          - powerschool
          - u_expectations
  external:
    location:
      "{{ var('powerschool_external_location_root',
      env_var('DBT_DEV_CLOUD_STORAGE_URI_BASE', '')) }}/u_expectations/*"
    options:
      connection_name: "{{ var('bigquery_external_connection_name') }}"
      metadata_cache_mode: MANUAL
      max_staleness: INTERVAL 7 DAY
      format: AVRO
      enable_logical_types: true
```

After this change, run `dbt run-operation stage_external_sources` against the
target environment per the project-wide external-table convention.

### 3. dbt staging model (shared package)

Two new files in the shared `dbt/powerschool/` source-system package — the
standard home for PS extension tables, mirroring `stg_powerschool__u_clg_et_stu`
and friends:

- `src/dbt/powerschool/models/sis/staging/odbc/stg_powerschool__u_expectations.sql`
- `src/dbt/powerschool/models/sis/staging/odbc/properties/stg_powerschool__u_expectations.yml`
  (path pattern follows the rest of the package — verify exact `properties/`
  subdirectory location during implementation).

#### SQL

```sql
with
    transformations as (
        select
            * except (dcid, id),

            dcid.int_value as dcid,
            id.int_value as id,
        from {{ source("powerschool_odbc", "src_powerschool__u_expectations") }}
    )

select * from transformations
```

The `* except (...)` + `.int_value` unwrap handles the Avro-encoded Oracle
NUMBER type (which lands as a struct with `int_value` / `decimal_value`
siblings), matching the existing PS staging precedent. Additional `safe_cast`
may be needed for `cnt_w` / `cnt_h` / `cnt_f` / `cnt_s` if Oracle stores them as
NUMBER without a fixed scale — finalize during implementation after profiling
the loaded BQ external table.

#### Properties YAML

- `description:` on the model and every column.
- `data_type:` for every column (BigQuery contract types: `int64`, `string`,
  `timestamp`, etc.).
- `dcid` carries `unique` and `not_null` data tests, both with
  `config: { severity: error }`.
- Contract enforcement is inherited from the staging directory's
  `dbt_project.yml` config — no per-model override needed.

Issue-specified payload columns (`id`, `school_level`, `quarter`, `week_number`,
`cnt_w`, `cnt_h`, `cnt_f`, `cnt_s`, `notes`) plus the standard PS audit columns
(`dcid`, `whencreated`, `whenmodified`, etc.) all get contract entries.

### 4. District opt-outs

The Gradebook Audit plugin is only on Newark prod, so the asset/source/model
must be disabled in the other three districts' `dbt_project.yml` files —
following the precedent established for `u_clg_et_stu`, `u_def_ext_students`,
etc.

In each of `src/dbt/kippcamden/dbt_project.yml`,
`src/dbt/kippmiami/dbt_project.yml`, and `src/dbt/kipppaterson/dbt_project.yml`,
add:

- under `models.powerschool.sis.staging.odbc`:
  `stg_powerschool__u_expectations: { +enabled: false }`
- under `sources.powerschool.staging.odbc.powerschool_odbc`:
  `src_powerschool__u_expectations: { +enabled: false }`

`kippnewark` requires no override — it's enabled by default in the package.

### 5. End-to-end test

Add a test in `tests/assets/test_assets_powerschool_sis.py` mirroring
`test_u_studentsuserfields_kippnewark`:

```python
def test_u_expectations_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_partitioned_asset(
        assets=assets,
        asset_name="u_expectations",
        code_location=CODE_LOCATION.upper(),
    )
```

Materializes a random fiscal-year partition of the asset against Newark prod via
the existing SSH/ODBC integration-test fixtures. Run locally with
`OP_SERVICE_ACCOUNT_TOKEN` set; not run in CI.

### 6. No schedule / sensor changes

The existing fiscal-year partitioned PS sensor already covers any asset present
in `powerschool_table_assets_full`. No new schedule, sensor, or job. No
intermediate or mart model — per the issue, downstream modeling is deferred ("if
this works, we will formally write up a plan").

## Verification

Implementation is complete when:

1. `uv run dagster definitions validate -m teamster.code_locations.kippnewark.definitions`
   passes (asset wiring is well-formed).
2. `uv run pytest tests/assets/test_assets_powerschool_sis.py::test_u_expectations_kippnewark`
   passes locally (with `OP_SERVICE_ACCOUNT_TOKEN` set), confirming a real
   Oracle round-trip and Avro write-out against Newark prod.
3. The asset materializes successfully in branch deployment against Newark prod
   (latest fiscal-year partition fills with > 0 rows).
4. `uv run dbt build --select stg_powerschool__u_expectations --project-dir src/dbt/kippnewark`
   passes against the branch-deployment-loaded raw table — uniqueness on `dcid`
   and contract enforcement both hold.
5. The same `dbt build` selector run against `src/dbt/kippcamden`,
   `src/dbt/kippmiami`, and `src/dbt/kipppaterson` resolves to "model is
   disabled" rather than building or erroring (confirms opt-out wiring).
6. The raw asset's BQ row count and the staging model's row count match.

If the Oracle table's exact name turns out to be schema-qualified (e.g.,
`U_GRADEBOOK_AUDIT.U_EXPECTATIONS`) or otherwise differs, adjust the
`asset_name` in the YAML. The factory passes the value to SQLAlchemy `table()`,
which auto-uppercases unquoted identifiers; lowercase `u_expectations` resolves
to `U_EXPECTATIONS` in Oracle.

## Risks

- **Table not yet present on Newark prod**: first scheduled materialization
  fails with `ORA-00942`. Caught by branch-deployment validation before merging.
- **Avro-typed numeric edge cases**: counts (`cnt_*`) may need `safe_cast` if
  Oracle stores them as `NUMBER` without explicit scale — handled in the SQL
  during implementation, not blocking design.
- **Plugin re-installation churn**: the issue notes the table is created
  manually via the PS Database Extensions UI on CLG-hosted instances. If the
  plugin is reinstalled and the table is dropped, the extract fails until it's
  recreated. Out of scope for this spec.

## Out of scope

- `U_FLAGS` / `U_EXCEPTIONS` — Phase 2 / Phase 3 follow-ups, same pattern.
- kippcamden / kippmiami / kipppaterson — when the plugin is installed there.
- Intermediate / mart / Tableau-facing models on top of `u_expectations`.
- Migration of the existing Gradebook Audit pipeline to PS-native logic.
