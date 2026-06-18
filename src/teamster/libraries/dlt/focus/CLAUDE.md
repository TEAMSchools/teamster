# CLAUDE.md — `teamster/libraries/dlt/focus/`

Loads tables from the **Focus SIS** PostgreSQL database directly to BigQuery
using dlt's `sql_database` source with PyArrow backend.

## Factory

`build_focus_dlt_assets(sql_database_credentials, code_location, table_name)`

- Asset keys: `[code_location, "dlt", "focus", table_name]`
- Uses `reflection_level="full_with_precision"` + `remove_nullability_adapter`
- All tables from the `public` schema (Focus default)

## Differences from Illuminate

| Aspect              | Illuminate                              | Focus                        |
| ------------------- | --------------------------------------- | ---------------------------- |
| Schema dimension    | Multi-schema (asset key includes it)    | Single `public` schema       |
| Type adapters       | `unbounded_numeric_adapter`             | None (full_with_precision)   |
| Query callbacks     | `filter_date_taken_callback` (optional) | None                         |
| Nullability adapter | `remove_nullability_adapter`            | `remove_nullability_adapter` |

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

## Testing Constraints

Focus uses an IP allowlist. Codespace cannot reach the database. Connection
verification requires a branch deployment (GKE has static egress IP).
