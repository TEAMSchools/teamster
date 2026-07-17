# CLAUDE.md — `teamster/libraries/dlt/`

DLT (data load tool) pipeline assets for source systems that use the
`dagster-dlt` integration. Each sub-library wraps a DLT source + custom
`DagsterDltTranslator` to control asset keys.

## Sub-libraries

### `illuminate/`

Loads tables from the **Illuminate** (assessment platform) PostgreSQL database
directly to BigQuery using `dlt`'s `sql_database` source with PyArrow backend.

- Asset keys: `[code_location, "dlt", "illuminate", schema, table]`
- `filter_date_taken_callback` handles a PostgreSQL `infinity` date value in
  certain tables that breaks psycopg
- Factory:
  `build_illuminate_dlt_assets(sql_database_credentials, code_location, schema, table_name)`

### `focus/`

Loads tables from the **Focus SIS** (student information system) PostgreSQL
database directly to BigQuery using `dlt`'s `sql_database` source with PyArrow
backend.

- Asset keys: `[code_location, "dlt", "focus", table_name]`
- Uses `reflection_level="full_with_precision"` + `remove_nullability_adapter`
  (forces all columns `NULLABLE` so upstream `NOT NULL` changes don't break the
  `replace` load — see `focus/CLAUDE.md`)
- Factory:
  `build_focus_dlt_assets(sql_database_credentials, code_location, table_name)`

### `salesforce/`

Loads Salesforce objects to BigQuery. Pipeline and helpers are adapted from the
`dlt` Salesforce source. Currently commented out / inactive in `kipptaf`.

### `zendesk/`

Loads Zendesk Support data (tickets, users, organizations, etc.) to BigQuery
using a vendored DLT Zendesk pipeline.

- Asset keys: `[code_location, "dlt", "zendesk", "support", resource_name]`
- Factory:
  `build_zendesk_support_dlt_assets(zendesk_credentials, code_location)`
- Vendored pipeline in `zendesk/pipeline/` handles auth via
  `TZendeskCredentials` and API pagination

### `powerschool/`

Loads PowerSchool SIS Oracle tables to BigQuery over an SSH tunnel
(`table_rows` + PyArrow), probe-gated full-replace. Factory:
`build_powerschool_dlt_assets(code_location, tables, op_tags=None, max_extract_workers=None)`;
asset keys `[code_location, "powerschool", "sis", table]`.

- **Single-tunnel data-volume ceiling**: a single-stream `table_rows` pull of a
  large table (`assignmentscore` ~19M) dies with `oracledb DPY-4011` (connection
  closed) at a consistent **~8.6M rows**, independent of throughput or elapsed
  time — `arraysize=10k` hit the wall at ~245s (~35k rows/s), `arraysize=50k` at
  ~158s (~60k rows/s), same ~8.6M rows. So it is a per-connection/tunnel VOLUME
  cap (the single in-process paramiko tunnel), NOT a duration or concurrency
  limit (a 5→1 `EXTRACT__WORKERS` sweep all failed at the same volume).
  `arraysize` raises throughput but only reaches the wall sooner. Naive
  full-replace only works for tables under the cap; larger tables need
  windowed/partitioned extraction (each window < the cap) — the retired ODBC
  path partitioned by fiscal year for exactly this reason. dlt extract
  concurrency is set via `EXTRACT__WORKERS` (dlt config/env; `pipeline.run()`
  does NOT accept a `workers` arg — only `pipeline.extract()` does).

## Notes

All DLT assets use `DagsterDltResource` (from `dagster-dlt`) and write directly
to BigQuery — they do not go through the GCS IO managers.

### Illuminate: unbounded Postgres `numeric`

Postgres `numeric` with no precision/scale reflects as `precision=None` in
SQLAlchemy. DLT defaults to `decimal128(38, 9)`, which truncates values with >9
decimal places. `unbounded_numeric_adapter` in `illuminate/assets.py` handles
this via `type_adapter_callback`, widening to `decimal128(38, 18)`.

**BigQuery type mapping**: `Numeric(38, 18)` maps to `BIGNUMERIC` (scale > 9),
not `NUMERIC`. Fix pattern: cast at the dbt staging layer
(`cast(col as numeric)`) so contracts and downstream models stay on `numeric`.
If the adapter's scale changes, any existing BQ table with a conflicting column
type must be dropped manually — `replace` write disposition does not allow type
changes on existing tables.

### `replace` write-disposition + runtime subsetting (dlt 1.28.1)

- A `replace` resource that yields **zero rows truncates** its destination table
  — you cannot skip a table by yielding nothing from inside the run. To load a
  runtime-chosen subset, exclude the others from the run entirely: pass a
  narrowed source to
  `DagsterDltResource.run(dlt_source=source.with_resources(*subset))` (its
  `is_subset` filter intersects with `selected_asset_keys`).
- `replace` never changes an existing table's column **mode** (not just type):
  an all-`NULLABLE` load into a table whose column is `REQUIRED` fails with BQ
  400 "changed mode from REQUIRED to NULLABLE". Drop the table so the pipeline
  recreates it (same remedy as the type-change note above).
- `dataset_name` (e.g. `dagster_<loc>_dlt_*`) is **not branch-isolated** —
  branch-deployment runs write to the SAME dataset as prod, so branch testing
  pollutes it and schema-mode mismatches recur at prod go-live. Plan a one-time
  `DROP SCHEMA ... CASCADE` cutover when a new pipeline replaces an old one.
- A `@dlt.source` yielding two resources with the **same name** raises
  `InvalidResourceDataTypeMultiplePipes`; build one resource per table with a
  distinct `name=` (or `.with_name()`, which sets both `name` and `table_name`).
- **`parallelized=True` is compatible with `resource_state` writes** — that is
  the documented incremental pattern (write `dlt.current.resource_state()[...]`
  in the resource body; the value persists per-thread). What breaks is **nesting
  a `DltResource` inside a `parallelized` resource**
  (`yield from sql_table(...)`): concurrent worker threads mangle dlt's
  per-resource injectable context (`ContainerInjectableContextMangled` /
  "generator already executing"). To parallelize a `sql_table`-style extract
  while still writing `resource_state`, don't wrap the resource — drive the
  exported **`table_rows`** generator directly inside your own
  `@dlt.resource(parallelized=True)`:
  `from dlt.sources.sql_database.helpers import table_rows`. It's a plain
  generator (no resource nesting) and takes the same `reflection_level` /
  `table_adapter_callback` / `type_adapter_callback` args, so
  decimal/nullability adapters and precision reflection are preserved. Caveat:
  `table_rows` is a lower-level building block with a broad, semi-internal
  signature (Pyright flags it as not top-level exported) — pin the dlt version
  and pass every positional arg explicitly, since arg changes there would
  surface on upgrade. A duckdb spike yielding plain rows will pass and miss the
  nesting mangle — it only fires with a nested resource on a real run.
- **dlt commits state only from a resource actually extracted into the load**
  (serial main-thread OR a `parallelized` worker). Writes from the `@dlt.source`
  function body or a `selected=False` resource never round-trip
  (spike-confirmed, silent) — this is why the per-table signature write lives
  inside the extracted resource, not the source.
- `.fetch_row_count()` on the `run()` iterator adds per-table `row_count`
  metadata; log `pipeline.last_trace.last_normalize_info.row_counts` in an
  `except` so a load failure is legible without walking the exception chain.
- **Stream dlt progress into the Dagster event log**: in the op, set
  `dlt_pipeline.collector = LogCollector(logger=context.log, log_period=30.0)`
  (`context.log` is a `logging.Logger`). The factory default `logger="stdout"`
  reaches only step-pod compute logs, so the UI goes dark mid-load. Gotcha:
  `log_period` throttles only _repeat_ dumps of the **same** counter — each new
  table force-logs (dlt's `update()` resets `last_log_time=None` on a new
  counter), so per-table bursts at Extract/Normalize phase starts are
  unavoidable; `log_period` only quiets the long Load phase. Dropping it
  defaults to 1.0s -> a chatty Load phase.
