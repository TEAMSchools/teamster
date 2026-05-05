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
- Uses `reflection_level="full_with_precision"` — no custom type or nullability
  adapters
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
