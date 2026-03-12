# Architecture

## Project structure

All source code is in the `src/` directory.

`src/teamster/` contains all Dagster code, organized as:

- `core/` — shared resources, IO managers, and utilities
- `libraries/` — reusable asset builders and resource definitions (one
  subpackage per integration)
- `code_locations/` — per-school Dagster definitions (`kipptaf`, `kippnewark`,
  `kippcamden`, `kippmiami`, `kipppaterson`)

`src/dbt/` contains all dbt code, organized by
[project](https://docs.getdbt.com/docs/build/projects).

## dbt Projects

`kipptaf` is the homebase for all CMO-level reporting. This project contains
views that aggregate regional tables as well as CMO-specific data. This is the
**only** project that dbt Cloud is configured to work with.

`kippnewark`, `kippcamden`, `kippmiami`, and `kipppaterson` contain regional
configurations that ensure their data is loaded into their respective datasets.

Other projects (e.g. `powerschool`, `deanslist`, `iready`) contain code for
systems used across multiple regions. Keeping these projects as installable
dependencies allows the code to be maintained in one place and shared across
projects.
