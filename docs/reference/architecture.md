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

### kipptaf schema layout

`dbt_project.yml` applies directory-level `+schema` overrides that control which
BigQuery dataset a model lands in. These are inherited — do not repeat them
per-model unless overriding:

| Directory           | BigQuery dataset    |
| ------------------- | ------------------- |
| `extracts/tableau/` | `kipptaf_tableau`   |
| `extracts/`         | `kipptaf_extracts`  |
| `reporting/`        | `kipptaf_reporting` |
| Everything else     | `kipptaf`           |

!!! note

    `reporting/` has no contract or materialization defaults — it is **not** where `rpt_` models live. `rpt_` models live in `extracts/`.

### kipptaf dbt asset groups

`kipptaf` splits dbt into four separate `@dbt_assets` groups with different
resource requirements and selection criteria:

| Variable                  | `select`              | `exclude`                                             | CPU   |
| ------------------------- | --------------------- | ----------------------------------------------------- | ----- |
| `core_dbt_assets`         | `fqn:*`               | `source:adp_payroll+`, `tag:google_sheet`, `extracts` | 2000m |
| `reporting_dbt_assets`    | `extracts`            | `source:adp_payroll+`                                 | 1750m |
| `google_sheet_dbt_assets` | `tag:google_sheet`    | —                                                     | —     |
| `adp_payroll_dbt_assets`  | `source:adp_payroll+` | —                                                     | —     |

`core_dbt_assets` is the canonical group — it is the one Tableau workbook
dependencies are resolved against.

### PowerSchool integration

PowerSchool has two live integration paths, plus a retired one:

| Integration    | Protocol               | Schools        | Notes                                              |
| -------------- | ---------------------- | -------------- | -------------------------------------------------- |
| SIS via dlt    | Oracle over SSH tunnel | Newark, Camden | Current pattern; replaces the ODBC path below      |
| SIS via SFTP   | File ingestion         | Paterson only  | Schema-only use case                               |
| Enrollment API | REST                   | All            | Separate from SIS; handles form submission records |

**Miami** no longer runs a live PowerSchool SIS integration — its pre-Focus
PowerSchool data is archived in the frozen BigQuery dataset
`kippmiami_powerschool` (do not drop). SIS via ODBC (Oracle over a live SSH
tunnel) is archived — the code and dbt models remain in place but no district
builds them.

### PowerSchool regional extracts

`rpt_powerschool__autocomm_*` models in `kipptaf/models/extracts/powerschool/`
define a shared export file format consumed by regional PowerSchool instances.
These models are **not** extracted in `kipptaf` — the regional projects
(`kippnewark`, `kippcamden`) each source from them, filter to their own data,
and push to their respective PowerSchool instance. Miami retired its PowerSchool
instance (frozen archive in BigQuery dataset `kippmiami_powerschool`) and no
longer sources these extracts.

As a result, dbt exposures for PowerSchool extracts live in the **regional
projects**, not in `kipptaf`.
