---
hide:
  - navigation
---

# Getting Started

## Account Setup

### GitHub

To contribute, you must be a member of our
[Data Team](https://github.com/orgs/TEAMSchools/teams/data-team). Your ability
to approve and merge pull requests depends on your subgroup:

- [Analytics Engineers](https://github.com/orgs/TEAMSchools/teams/analytics-engineers)
- [Data Engineers](https://github.com/orgs/TEAMSchools/teams/data-engineers)
- [Admins](https://github.com/orgs/TEAMSchools/teams/admins)

### Google Workspace

To access our BigQuery project and its datasets, you must be a member of the
**TEAMster Analysts KTAF** Google security group.

### dbt Cloud

#### Development dataset

dbt Cloud creates a personal development dataset in BigQuery for each user,
named using your username as a prefix. Please prefix yours with an underscore
(`_`) — BigQuery hides datasets starting with `_` from the left nav, keeping the
project list readable.

Set this in **Account settings → Credentials → Development credentials**.

#### sqlfmt

<!-- adapted from https://docs.getdbt.com/docs/cloud/dbt-cloud-ide/lint-format#format-sql -->

We use [sqlfmt](https://sqlfmt.com/) for SQL formatting. To enable it in dbt
Cloud:

1. Open a `.sql` file on a development branch.
2. Click the **Code Quality** tab in the console, then **`</> Config`**.
3. Select the `sqlfmt` radio button.
4. Click **Format** to auto-format the file.

## GitHub Codespaces

See the [Codespaces guide](guides/codespaces.md) for full setup instructions.

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

### Linting and formatting

[Trunk](https://trunk.io/) runs all linters:

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
