# CLAUDE.md — `teamster/libraries/dlt/focus/`

Loads tables from the **Focus SIS** PostgreSQL database directly to BigQuery
using dlt's `sql_database` source with PyArrow backend.

## Factory

`build_focus_dlt_assets(sql_database_credentials, code_location, table_name)`

- Asset keys: `[code_location, "dlt", "focus", table_name]`
- Uses `reflection_level="full_with_precision"` — no custom type adapters
- No custom callbacks — add only if Postgres-specific issues surface
- All tables from the `public` schema (Focus default)

## Differences from Illuminate

| Aspect              | Illuminate                              | Focus                      |
| ------------------- | --------------------------------------- | -------------------------- |
| Schema dimension    | Multi-schema (asset key includes it)    | Single `public` schema     |
| Type adapters       | `unbounded_numeric_adapter`             | None (full_with_precision) |
| Query callbacks     | `filter_date_taken_callback` (optional) | None                       |
| Nullability adapter | `remove_nullability_adapter`            | None (full_with_precision) |

## Testing Constraints

Focus uses an IP allowlist. Codespace cannot reach the database. Connection
verification requires a branch deployment (GKE has static egress IP).
