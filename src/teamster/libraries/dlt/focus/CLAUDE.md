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
  `Cannot add required fields to an existing schema`), which is why the rollout
  recreated all populated tables once via run config `refresh: drop_resources`.
  Any future table created outside this path needs the same treatment.
- **Column order differs** between a table created empty (`_dlt_*` first) and
  one created by a data load (`_dlt_*` last). Cosmetic — loads match by name and
  every staging model projects explicitly.
- A table absent from `dagster_<district>_dlt_focus` now means a **config or
  load problem**, not an empty source. That is the diagnostic this change buys.
- A table that empties out AFTER loading is truncated, not dropped — see
  `replace` write-disposition in `../CLAUDE.md` (#4733).

The resource yields hints defensively before the marker so reflection items
reach dlt in a single batch — that ordering simplifies the architecture but the
columns survive either way (dlt absorbs hints that arrive later too). Columns
are lost only when `table_rows` never yields any items at all, so no reflection
reaches dlt.

## Testing Constraints

Focus uses an IP allowlist. Codespace cannot reach the database. Connection
verification requires a branch deployment (GKE has static egress IP).

Branch-deployment dlt runs write to the **prod** BQ dataset
(`dagster_<district>_dlt_focus`) — dlt has no branch-deployment redirect (unlike
the GCS IO managers). A newly-configured table can be materialized in the branch
deployment and then queried directly via BigQuery MCP to verify the load; note
it is not isolated from prod for that source.
