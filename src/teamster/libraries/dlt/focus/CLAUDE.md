# CLAUDE.md — `teamster/libraries/dlt/focus/`

Loads tables from the **Focus SIS** PostgreSQL database directly to BigQuery by
driving dlt's `table_rows` generator directly (not the `sql_database` source),
with the PyArrow backend, probe-gated same as `powerschool/`. Factory signature
and asset keys: see `../CLAUDE.md`. All tables come from the `public` schema
(Focus default).

## Differences from Illuminate

| Aspect              | Illuminate                              | Focus                              |
| ------------------- | --------------------------------------- | ---------------------------------- |
| Schema dimension    | Multi-schema (asset key includes it)    | Single `public` schema             |
| Type adapters       | `unbounded_numeric_adapter`             | `interval_to_microseconds_adapter` |
| Query callbacks     | `filter_date_taken_callback` (optional) | None                               |
| Nullability adapter | `remove_nullability_adapter`            | `remove_nullability_adapter`       |

## Nullability adapter (required)

`full_with_precision` reflects Postgres `NOT NULL` into BigQuery `REQUIRED`
mode. BigQuery forbids both adding a `REQUIRED` column and relaxing an existing
`REQUIRED` column to `NULLABLE`, so any upstream nullability change breaks the
`replace` load (it migrates schema in place, never drops the table). Passing
`table_adapter_callback=remove_nullability_adapter` makes every column
`NULLABLE`, so schema evolution never hits a `REQUIRED`-mode constraint — the
same fix Illuminate uses. Adding/removing this adapter against existing tables
that already have `REQUIRED` columns requires dropping those tables first
(`replace` repopulates them on the next run).

## Interval adapter (required)

Postgres `interval` matches none of the branches in dlt's
`sqla_col_to_column_schema`, so the reflected column carries no `data_type`, the
PyArrow backend infers `duration[us]` from the `timedelta` values, and the load
dies with `UnsupportedArrowTypeException` (#4676 —
`gradebook_assignments.time_limit`).
`type_adapter_callback=interval_to_microseconds_adapter` declares `BigInteger`,
so **every Focus `interval` column lands as BigQuery INT64 microseconds** —
divide by `1e6` for seconds when consuming one downstream.

Not `Time`: dlt converts duration to `time64` by reinterpreting the buffer,
which silently corrupts intervals of 24 hours or more and negative intervals.

`_AbstractInterval` is the isinstance check —
`isinstance(postgresql.INTERVAL(), sqltypes.Interval)` is `False`, so the
obvious check silently matches nothing. It imports only from
`sqlalchemy.sql.sqltypes`.

Unlike the nullability adapter, this one needs no table drop: the new column
arrives NULLABLE, which `replace` may add.

**An all-NULL `interval` column loads fine and is silently dropped**, so absence
from BigQuery does NOT mean the column is new. pyarrow infers arrow `null`,
which dlt maps to no `data_type` and omits from the destination; the load breaks
only when the FIRST non-null value lands. That is why #4676's asset succeeded at
08:04 UTC and failed at 22:31 on the same commit — one assignment populated
`time_limit` at 13:23. Two consequences: don't date a schema change from the
BigQuery column set, and other Focus tables may hold unpopulated `interval`
columns that break on first use, which you cannot enumerate from BigQuery. Hence
the adapter keys off the reflected type for every table rather than naming
columns.

## Empty source tables

A configured table with 0 rows in Focus is **created empty** in BigQuery: the
resource in `assets.py` appends `dlt.mark.materialize_table_schema()` when
`table_rows` yielded no data, so the table exists from the reflected schema and
a staging model can be written before any data arrives (#4740).

Consequences to know:

- **Every Focus table carries `_dlt_id` and `_dlt_load_id`.** The materialize
  marker travels dlt's object path, which injects both as REQUIRED, so the arrow
  data path must supply them too — hence the two
  `normalize.parquet_normalizer.add_dlt_*` knobs set in the op body. Turning
  either off breaks the first real load into an empty-created table with
  `Field _dlt_load_id is missing in new schema`.
- **Adding those columns to an existing table is impossible** (BigQuery:
  `Cannot add required fields to an existing schema`), so every table that was
  already populated has to be recreated once, by launching the Focus asset job
  with run config `refresh: drop_resources`. Any table that predates that
  migration, or is created outside this path, needs the same treatment.
- **Until that migration runs, every already-populated table FAILS to load.**
  The knobs are pipeline-wide: the arrow normalizer stamps both columns
  non-nullable into every load file, and dlt's BigQuery load job sets
  `ALLOW_FIELD_ADDITION` without `ALLOW_FIELD_RELAXATION`, so BigQuery rejects
  each one. Deploying this code and deferring the migration is a prod outage,
  not a no-op — sequence the two together.
- A table absent from `dagster_<district>_dlt_focus` now means a **config or
  load problem**, not an empty source. That is the diagnostic this change buys.
- A table that empties out AFTER loading is truncated, not dropped — see
  `replace` write-disposition in `../CLAUDE.md` (#4733).

The resource yields hints defensively before the marker so reflection items
reach dlt in a single batch — that ordering simplifies the architecture but the
columns survive either way (dlt absorbs hints that arrive later too). Columns
are lost only when `table_rows` never yields any items at all, so no reflection
reaches dlt.

## Probe gating

One `@dlt_assets` op covers every Focus table; the intraday sensor decides which
of them a run carries. A table is loaded only when its probed signature
(`COUNT(*)` + `MAX(updated_at)`) differs from the one the last successful load
wrote to dlt `resource_state`.

- **Gating cannot move into the op.** A `replace` resource that yields zero rows
  truncates its table, so a skip has to be an exclusion from the run. Probing in
  the op would also plan all 77 assets every tick and emit
  `ASSET_FAILED_TO_MATERIALIZE` for the skipped ones.
- **The signature is written inside the extracted resource.** dlt commits state
  only from resources that reached the load package, so a failed load keeps the
  old baseline and the table re-selects on the next tick — failures self-heal.
- **A 0-row table** carries `{count: 0, max_cursor: null}` and gates out after
  its first load, so the empty-table materialization runs once, not every tick.
  Verified: dlt does commit resource_state for a table that yields only
  reflection hints plus the materialize marker — pinned by
  `tests/libraries/test_dlt_focus_signature_state.py::test_empty_table_persists_its_signature`,
  so a dlt upgrade that changes it fails CI. That test seeds a sqlite source
  (Focus sits behind an IP allowlist unreachable from the codespace) and calls
  only `pipeline.extract()` — it verifies dlt's state-commit mechanics, not the
  real BigQuery `_dlt_loads` / `_dlt_pipeline_state` round-trip through a full
  load. That end-to-end path is still an open branch-deployment validation item
  (see the design spec's _Partially resolved risk_ section).
- **Enable order matters.** The sensor selects any table with no stored
  signature, so enabling it before every table has a seeded baseline makes the
  first tick select all 77 tables at once. The `0 4 * * *` schedule now only
  seeds the two count-only tables (`co_teachers`, `login_history`) — it is no
  longer a full-77-table refresh, so it cannot be relied on to seed the other 75
  by itself. Seed all 77 with a manual launch of the Focus asset job first, then
  enable the sensor.

## Testing Constraints

Focus uses an IP allowlist. Codespace cannot reach the database. Connection
verification requires a branch deployment (GKE has static egress IP).

Branch-deployment dlt runs write to the **prod** BQ dataset
(`dagster_<district>_dlt_focus`) — dlt has no branch-deployment redirect (unlike
the GCS IO managers). A newly-configured table can be materialized in the branch
deployment and then queried directly via BigQuery MCP to verify the load; note
it is not isolated from prod for that source.
