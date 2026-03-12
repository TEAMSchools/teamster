# IO Managers

Teamster uses a custom `GCSIOManager` that extends `dagster-gcp`'s
`PickledObjectGCSIOManager`. All intermediate asset outputs are stored in Google
Cloud Storage buckets named `teamster-<code_location>` (e.g.
`teamster-kipptaf`).

Branch deployments automatically redirect to the `teamster-test` bucket to
isolate test runs from production data.

## Choosing an IO manager

Three modes are available. Each code location wires them up via factory
functions in `core/resources.py`:

| IO manager           | Factory                                    | `object_type` | Use when                                                                   |
| -------------------- | ------------------------------------------ | ------------- | -------------------------------------------------------------------------- |
| **Pickle** (default) | `get_io_manager_gcs_pickle(code_location)` | `"pickle"`    | Python objects (dicts, dataframes, etc.) — the default for most assets     |
| **Avro**             | `get_io_manager_gcs_avro(code_location)`   | `"avro"`      | SFTP and API assets that yield lists of records with a defined Avro schema |
| **File**             | `get_io_manager_gcs_file(code_location)`   | `"file"`      | Raw bytes from a local file path — used by paginated Deanslist assets      |

## GCS path structure

Asset outputs are stored using Hive-style partitioned paths so that BigQuery
external tables can read them directly.

**Date/datetime partition keys** are decomposed into fiscal year, date, hour,
and minute components:

```
teamster-<code_location>/
  <asset_key>/
    _dagster_partition_fiscal_year=YYYY/
      _dagster_partition_date=YYYY-MM-DD/
        _dagster_partition_hour=HH/
          _dagster_partition_minute=MM/
            data
```

**Non-date partition keys** use a single key component:

```
teamster-<code_location>/
  <asset_key>/
    _dagster_partition_key=<value>/
      data
```

**Multi-partition keys** concatenate all dimensions, sorted alphabetically by
dimension name.

## Resync signal

The epoch timestamp `1970-01-01` is treated as a full-refresh trigger. When the
`GCSIOManager` writes a partition with this key, it replaces the timestamp with
the current time, effectively writing to a fresh path.

**How to use it**: To force a complete refresh of a partitioned asset without
deleting existing GCS data, materialize the asset using `1970-01-01` as the
partition key. The IO manager writes to a new timestamped path; downstream
BigQuery external tables pick up the new data on the next query.

This is the standard pattern for assets where the upstream API does not support
incremental queries and a periodic full reload is required.
