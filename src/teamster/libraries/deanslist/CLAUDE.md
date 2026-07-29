# CLAUDE.md — `teamster/libraries/deanslist/`

Dagster assets and resource for the **Deanslist** behavior management platform.
Assets are school-partitioned (each school has its own Deanslist subdomain and
API key).

## Factory Functions

Three builders cover different endpoint access patterns:

| Function                                            | Partition type                              | Use case                                                               |
| --------------------------------------------------- | ------------------------------------------- | ---------------------------------------------------------------------- |
| `build_deanslist_static_partition_asset()`          | `StaticPartitionsDefinition` (school IDs)   | Simple per-school endpoints                                            |
| `build_deanslist_multi_partition_asset()`           | `MultiPartitionsDefinition` (school × date) | Date-windowed endpoints using `UpdatedSince` / `StartDate` / `EndDate` |
| `build_deanslist_paginated_multi_partition_asset()` | `MultiPartitionsDefinition`                 | Large paginated endpoints; uses `io_manager_gcs_file` instead of Avro  |

Date windows are computed from `FiscalYear` (July start). For
`MonthlyPartitionsDefinition`, `EndDate` is the last day of the month; for
`FiscalYearPartitionsDefinition`, it's the fiscal year end.

## `behavior` is config-invisible

`behavior` (the paginated endpoint) is wired directly in each district's
`assets.py` — `build_deanslist_paginated_multi_partition_asset` appended to
`year_partitioned_assets` — NOT in `config/*.yaml`. When adding deanslist to a
district or auditing endpoint parity, check `assets.py`; diffing only the config
YAMLs misses it (how Paterson shipped without behavior, #4376). A district using
it must also wire `io_manager_gcs_file` in `definitions.py`.

## Resource: `DeansListResource`

Configured with a single `api_key_dir` — a directory (the per-city
`op-deanslist-api-<district>` K8s secret mounted at `/etc/deanslist`) holding
one file per school (filename = `school_id`, contents = API key) plus a
`subdomain` file. `load_deanslist_config()` reads the subdomain and builds the
`{school_id: key}` map from numeric-named files. Provides `get()` and `list()`.
