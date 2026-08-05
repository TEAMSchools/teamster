# CLAUDE.md — `teamster/libraries/dlt/focus/`

Loads tables from the **Focus SIS** PostgreSQL database directly to BigQuery
using dlt's `sql_database` source with PyArrow backend. Factory signature and
asset keys: see `../CLAUDE.md`. All tables come from the `public` schema (Focus
default).

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

A 0-row source extract behaves differently before and after the table's first
successful load, because dlt's empty-table handling keys off
`seen_data_only=True`:

- **Never loaded data**: the PyArrow backend writes NO BigQuery table and no
  load jobs (the asset SUCCEEDS — no `rows_loaded`, `jobs: []`). A configured
  Focus table absent from `dagster_<district>_dlt_focus` is therefore **empty in
  the source** (Focus is mid-rollout in Miami), not an extraction failure —
  confirm via the asset materialization metadata before investigating.
- **Has loaded data before**: dlt emits an empty file so the `replace` root is
  truncated. That file must be parquet or BigQuery autodetection fails the load
  — hence `loader_file_format="parquet"` in `assets.py`. See _`replace`
  write-disposition_ in `../CLAUDE.md` (#4733).

So a Focus asset going quiet is not evidence the table is new, and a table
emptying out is not a data loss — the truncate is the intended outcome.

## Testing Constraints

Focus uses an IP allowlist. Codespace cannot reach the database. Connection
verification requires a branch deployment (GKE has static egress IP).

Branch-deployment dlt runs write to the **prod** BQ dataset
(`dagster_<district>_dlt_focus`) — dlt has no branch-deployment redirect (unlike
the GCS IO managers). A newly-configured table can be materialized in the branch
deployment and then queried directly via BigQuery MCP to verify the load; note
it is not isolated from prod for that source.
