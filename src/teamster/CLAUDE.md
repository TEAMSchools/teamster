# CLAUDE.md — `src/teamster/`

This file provides guidance to Claude Code (claude.ai/code) when working with
the Dagster Python package in this directory.

## Overview

```text
teamster/
  __init__.py             # GCS_PROJECT_NAME = "teamster-332318"
  core/                   # Shared infrastructure (IO managers, resources, utils)
  libraries/              # Reusable asset builders, resources, and schemas
  code_locations/         # Per-school Dagster definitions (kipptaf, kippnewark, etc.)
```

## Library + Code Location Pattern

Integrations follow a two-layer separation:

1. **`libraries/<integration>/`** — reusable factory functions, resource
   classes, Avro schemas, and sensors. Never import from a code location.
2. **`code_locations/<school>/<integration>/`** — calls the library factory with
   school-specific YAML config via `config_from_files()`. Wires assets into the
   code location's `definitions.py`.

This means adding a new school to an existing integration requires only YAML
config and a few lines of Python in the code location — no library changes.

## Library Categories

Libraries fall into four patterns based on how they ingest data:

| Pattern            | Libraries                                                                                  | How it works                                                    |
| ------------------ | ------------------------------------------------------------------------------------------ | --------------------------------------------------------------- |
| **SFTP file drop** | collegeboard, edplan, fldoe, iready, nsc, pearson, performance_management, renlearn, titan | `build_sftp_*_asset()` from `libraries/sftp/` + Avro schemas    |
| **REST API**       | coupa, deanslist, knowbe4, level_data, overgrad, smartrecruiters                           | Custom `build_*_asset()` factory + resource class               |
| **Framework**      | dbt, dlt, google, airbyte, fivetran                                                        | Dagster-native integration (`dagster-dbt`, `dagster-dlt`, etc.) |
| **Multi-access**   | adp (API + SFTP), amplify (API + SFTP), powerschool (ODBC + SFTP + API)                    | Multiple factories per product line                             |

Schema-only libraries (collegeboard, dayforce, fldoe, nsc, pearson,
performance_management) contain only Avro schemas — the asset is built in the
code location using the generic SFTP factory.

## Code Location Structure

Each code location follows the same layout:

```text
code_locations/<name>/
  CLAUDE.md          # Module-specific context (read before working here)
  __init__.py        # CODE_LOCATION, LOCAL_TIMEZONE, CURRENT_FISCAL_YEAR, DBT_PROJECT
  definitions.py     # Dagster Definitions object wiring everything together
  resources.py       # Location-specific resource instances (if any)
  dbt/assets.py      # dbt asset definitions
  <integration>/     # Per-integration assets, config YAML, optional sensors
```

**Identity constants** (defined in `__init__.py`):

| Constant              | Example (`kippnewark`)         |
| --------------------- | ------------------------------ |
| `CODE_LOCATION`       | `"kippnewark"`                 |
| `LOCAL_TIMEZONE`      | `ZoneInfo("America/New_York")` |
| `CURRENT_FISCAL_YEAR` | `2026`                         |

**GCS bucket**: `teamster-<code_location>` (redirects to `teamster-test` in
branch deployments).

## Resource Model

Resources are defined in two places:

- **`core/resources.py`** — shared singletons (BigQuery, GCS, DLT, Google
  Workspace, SFTP/SSH clients) and factories (IO managers, dbt CLI, PowerSchool
  SSH). Imported by every code location.
- **`code_locations/<name>/resources.py`** — location-specific resources (e.g.,
  kipptaf defines ADP WFN, Airbyte, Coupa, LDAP, Tableau, etc.). Only exists
  when a code location needs resources beyond the shared set.

## Asset Key Convention

`[code_location, integration, ...]` — e.g., `kippnewark/powerschool/students`,
`kipptaf/extracts/tableau/attendance_dashboard`.

## Automation Conditions

Defined in `core/automation_conditions.py`. Three dbt-specific builders sharing
a common skeleton (`_build_dbt_condition`):

- **`dbt_view_automation_condition()`** — triggers on `code_version_changed`,
  `newly_missing`, or `execution_failed`. Intentionally omits `any_deps_updated`
  since views are computed on read.
- **`dbt_union_relations_automation_condition()`** — for views using the
  `union_relations` macro. Adds recursive ancestor `code_version_changed`
  detection (but NOT `any_deps_updated`) to the view condition. Triggers only on
  code deploys, not data refreshes.
- **`dbt_table_automation_condition()`** — also triggers on upstream data
  changes, including through intermediate views (recursive lookthrough up to 10
  levels).

Non-dbt assets use `AutomationCondition.eager()` or sensor/schedule triggers.

## IO Managers

Three GCS IO manager modes (all in `core/io_managers/gcs.py`):

| Mode     | Use case                       | Output format          |
| -------- | ------------------------------ | ---------------------- |
| `pickle` | Default IO manager             | Pickled Python objects |
| `avro`   | SFTP/API assets                | Fastavro container     |
| `file`   | Paginated Deanslist, raw files | Raw bytes              |

All use Hive-style partitioned GCS paths
(`_dagster_partition_date=YYYY-MM-DD/data`).

## Common Patterns

**Avro schema validation**: All asset factories yielding Avro output call
`build_check_spec_avro_schema_valid()` + `check_avro_schema_valid()` from
`core/asset_checks.py` (warns on extra fields, doesn't fail).

**Partition key substitution**: SFTP assets use regex named groups in
`remote_dir_regex`/`remote_file_regex`. At runtime, named groups are replaced
with partition dimension values via `regex_pattern_replace()`.

**SFTP sensors**: List remote directories, match files against asset regexes,
extract partition keys from named groups, emit `RunRequest`s grouped by
`(job_name, partition_key)`.

**Fiscal year**: July 1 start. `FiscalYear` class and
`FiscalYearPartitionsDefinition` in `core/utils/classes.py`.
