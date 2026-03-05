# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Project Overview

Teamster is a data engineering platform for KIPP TEAM & Family Schools (Newark,
Camden, and Paterson, NJ & Miami, FL) built on **Dagster** (orchestration),
**dbt** (transformations), and **Google BigQuery** (warehouse), with Google
Cloud Storage (GCS) as the intermediate storage layer.

## Commands

### Development

```bash
# Install dependencies
uv sync --frozen

# Run Dagster webserver locally
uv run dagster dev

# Validate Dagster definitions for a code location
uv run dagster definitions validate -m teamster.code_locations.kipptaf.definitions

# Prepare and package a dbt project (must be done before running dbt assets)
uv run dagster-dbt project prepare-and-package --file src/teamster/code_locations/kipptaf/__init__.py
```

### Testing

```bash
# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_dagster_definitions.py

# Run a single test
uv run pytest tests/test_dagster_definitions.py::test_definitions_kipptaf

# Run asset-specific tests (require env vars / external connections)
uv run pytest tests/assets/test_assets_dbt.py
```

### Linting

```bash
# Trunk is used for linting (ruff, pyright)
trunk check
trunk fmt
```

## Architecture

### Repository Structure

```
src/
  teamster/          # Dagster project (Python package)
    __init__.py      # GCS_PROJECT_NAME constant
    core/            # Shared infrastructure
      resources.py   # Shared resource instances (BigQuery, GCS, SSH, dbt, IO managers)
      io_managers/   # Custom GCS IO managers (pickle, avro, file)
      utils/         # Utility classes (FiscalYear, partitions, JSON encoder)
    libraries/       # Reusable asset builders and resource definitions
      powerschool/   # PowerSchool SIS (ODBC via Oracle) and enrollment
      dbt/           # dbt asset builder (build_dbt_assets)
      google/        # Google Drive, Forms, Sheets resources
      ssh/           # SSH tunnel resource
      deanslist/     # Deanslist API resource
      ... (one subpackage per integration)
    code_locations/  # Per-school Dagster definitions
      kipptaf/       # TAF (network-wide): the largest code location
      kippnewark/
      kippcamden/
      kippmiami/
      kipppaterson/
  dbt/               # dbt projects (one per data source or school network)
    kipptaf/         # Main network-wide dbt project
    kippnewark/      # School-specific dbt project
    kippcamden/
    kippmiami/
    kipppaterson/
    powerschool/     # Source-system dbt projects (shared)
    deanslist/
    ... (one project per data source)
```

### Key Architectural Patterns

**Code Location Pattern**: Each school network has a `code_locations/<name>/`
directory with:

- `__init__.py` — defines `CODE_LOCATION`, `LOCAL_TIMEZONE`,
  `CURRENT_FISCAL_YEAR`, `DBT_PROJECT`
- `definitions.py` — the `Definitions` object wiring all assets, schedules,
  sensors, resources
- `resources.py` — code-location-specific resource instances
- `_dbt/` — dbt asset definitions (loads manifest, builds `dbt_assets`)
- `_dlt/` — DLT pipeline assets
- `_google/` — Google Workspace assets
- Per-integration subdirectories (e.g., `powerschool/`, `deanslist/`)

**Library + Config Pattern**: Integrations follow a two-layer pattern:

1. `src/teamster/libraries/<integration>/assets.py` —
   `build_<integration>_asset()` factory function
2. `src/teamster/code_locations/<school>/<integration>/config/assets-*.yaml` —
   YAML files listing asset parameters
3. `src/teamster/code_locations/<school>/<integration>/assets.py` — calls the
   factory with `config_from_files()` for each YAML

**dbt Projects**: Each dbt project in `src/dbt/` corresponds to either a school
network (`kipptaf`, `kippnewark`, etc.) or a data source (`powerschool`,
`deanslist`, `renlearn`, etc.). School projects use `ref()` to pull from source
projects. The `kipptaf` project is the main analytics layer with staging,
intermediate, mart, and extract models.

**IO Managers**: Assets store intermediate data to GCS buckets named
`teamster-<code_location>`. Branch deployments automatically redirect to
`teamster-test`. Three IO managers exist: `pickle` (default), `avro`, and
`file`.

**Asset Keys**: Follow the pattern `[code_location, integration, table_name]`
(e.g., `kippnewark/powerschool/students`).

**Dagster Cloud deployment**: Each code location has a `dagster-cloud.yaml` and
is built as a separate Docker image using `CODE_LOCATION` build arg. Deployed to
Kubernetes with secrets mounted at `/etc/secret-volume`.

### dbt Project Conventions

- Models follow `stg_` (staging), `int_` (intermediate), `rpt_` (report/extract)
  prefixes
- `src/dbt/kipptaf/` is the primary analytics project; school-specific projects
  (`kippnewark`, etc.) contain school-specific extracts
- dbt packages are vendored into `dbt_packages/` subdirectories within each
  project
- Fiscal year starts July 1; `current_academic_year` and `current_fiscal_year`
  vars are set in `dbt_project.yml`
