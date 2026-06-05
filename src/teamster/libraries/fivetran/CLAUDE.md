# CLAUDE.md — `teamster/libraries/fivetran/`

Fivetran integration helpers for representing Fivetran-synced BigQuery tables as
Dagster `AssetSpec`s (external assets, not materialized by Dagster).

## Files

**`assets.py`** (`build_fivetran_asset_specs()`): Reads a YAML config file and
produces a list of `AssetSpec` objects — one per destination table. Asset keys
follow `[code_location, connector_name, (schema_name), table]`. Metadata
includes `connector_id`, `connector_name`, `dataset_id`, and `table_id`.

Config file format:

```yaml
connector_name: <name>
connector_id: <id>
group_name: <dagster_group>
schemas:
  - name: <optional_schema>
    destination_tables: [table1, table2]
```

**`sensors.py`**: Prototype sensor (completed-sync detection → asset
materialization events) — currently commented out / inactive.
