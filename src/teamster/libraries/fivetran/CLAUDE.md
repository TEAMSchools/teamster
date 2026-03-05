# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

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

**`schedules.py`**: Schedule that triggers a Fivetran sync via the connector API
(polling for completion). Used as an alternative to Fivetran's built-in
scheduler.

**`sensors.py`**: Sensor that detects completed Fivetran syncs and emits asset
materialization events.
