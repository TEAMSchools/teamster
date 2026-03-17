# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Project Overview

Teamster is a data engineering platform for KIPP TEAM & Family Schools (Newark,
Camden, and Paterson, NJ & Miami, FL) built on **Dagster** (orchestration),
**dbt** (transformations), and **Google BigQuery** (warehouse), with Google
Cloud Storage (GCS) as the intermediate storage layer.

## Working Conventions

- **Python execution**: Always use `uv run` — never bare `python` or `python3`,
  including inline one-liners (`uv run python -c "..."`, not
  `python3 -c "..."`). The project environment is managed by uv.
- **Git commits**: Do not commit proactively — ask first when a change is
  complete, tests are passing, and it is ready to commit, then commit if
  confirmed. Commits should have descriptive messages following the
  [conventional commit](https://www.conventionalcommits.org/en/v1.0.0/) format.
  Avoid checkpoint-style messages (`save`, `oops`, `update`, etc.).
- **Branch naming**: `<author>/<commit-type>/<brief-description>` (e.g.,
  `cbini/feat/salesforce-alumni-tracking`). Use `claude` as the author prefix
  for AI-assisted branches.
- **Pull requests**: Squash merge.
- **GitHub issues**: Do not open issues proactively — ask first when something
  warrants one, then open it if confirmed. Use `gh issue create` (not the web
  UI). Label it with a
  [conventional commit type](https://www.conventionalcommits.org/en/v1.0.0/)
  (`feat`, `fix`, `docs`, `refactor`, `chore`, etc.), any related source systems
  (e.g., `adp`, `powerschool`, `deanslist`), and `dagster` and/or `dbt` when
  applicable.

## Commands

The `scripts/` directory contains project utilities (doc generation, migrations,
etc.) in lieu of a Makefile. Run them with `uv run scripts/<name>.py`.

### Development

```bash
# Install dependencies
uv sync --frozen

# Inject 1Password secrets (required for Dagster development, not needed for SQL-only work)
.devcontainer/scripts/inject-secrets.sh

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

See `.trunk/trunk.yaml` for the full list of enabled linters and
`.trunk/config/` for per-linter configuration files. **Before committing**, run
`trunk check` on changed files and fix any issues — the pre-commit hook will
reject commits with linter errors.

**SQL style**: Before writing, reviewing, or commenting on SQL, read
`.trunk/config/.sqlfluff`. Key enforced rules: BigQuery dialect, trailing commas
**required** in SELECT clauses, single quotes for literals, max line length 88.
Do not flag code that follows these rules.

### BigQuery MCP Queries

The BigQuery MCP tool truncates results at 50 rows. When querying
`INFORMATION_SCHEMA.COLUMNS` for tables with >50 columns, paginate with
`WHERE ordinal_position > N` to get all rows.

## Documentation

Two documentation systems serve different audiences — do not conflate them:

- **dbt YAML** (properties files + exposures) — how analysts document models,
  columns, tests, and external tool dependencies. Required for all dbt model
  changes; enforced by the PR template checklist.
- **MkDocs site** (`docs/`) — how engineers document infrastructure patterns,
  architecture, and operational guides. Update when making engineering-level
  changes:
  - New integration → update `docs/reference/adding-an-integration.md` and the
    code location's `CLAUDE.md`
  - New or changed schedule/sensor → regenerate the automations catalog:
    `uv run scripts/gen-automations-doc.py`
  - New core pattern (IO manager behavior, automation condition, partitioning) →
    update the relevant `docs/reference/` page

Analysts adding or editing SQL models do not need to touch `docs/` — dbt YAML is
the documentation mechanism for that work.

## Architecture

**Before working on Dagster code**, read `src/teamster/CLAUDE.md` for
architecture, library patterns, and code location structure.

**Before working on dbt models**, read `src/dbt/CLAUDE.md` for project
structure, model conventions, and SQL standards.

Each subdirectory has its own CLAUDE.md — read it before modifying code in that
directory.
