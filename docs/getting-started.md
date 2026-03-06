# Getting Started

## Collaboration

- Asana
- 1Password
- GitHub

## Analytics Engineering

- dbt Cloud
- BigQuery
- Tableau

## Data Engineering

- Dagster
- dlt
- Airbyte
- VS Code (with
  [Dev Containers](https://code.visualstudio.com/docs/devcontainers/containers))

## Local Development

### Prerequisites

Install [uv](https://docs.astral.sh/uv/) for Python package management.

### Setup

```bash
# Install dependencies
uv sync --frozen

# Run Dagster webserver locally
uv run dagster dev

# Validate definitions for a code location
uv run dagster definitions validate -m teamster.code_locations.kipptaf.definitions
```

### dbt

Before running dbt assets locally, prepare and package the dbt project:

```bash
uv run dagster-dbt project prepare-and-package \
  --file src/teamster/code_locations/kipptaf/__init__.py
```

### Linting

[Trunk](https://trunk.io/) is used for linting and formatting:

```bash
trunk check   # lint
trunk fmt     # format
```

| Language | Linter(s)                                                                                   |
| -------- | ------------------------------------------------------------------------------------------- |
| SQL      | [SQLFluff](https://docs.sqlfluff.com/en/stable/rules.html), [sqlfmt](https://sqlfmt.com/)   |
| Python   | [Ruff](https://docs.astral.sh/ruff/rules/), [Pyright](https://github.com/microsoft/pyright) |

### Testing

```bash
# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_dagster_definitions.py

# Run asset-specific tests (require env vars / external connections)
uv run pytest tests/assets/test_assets_dbt.py
```

## Helpful Tools

- [RegExr](https://regexr.com/)
