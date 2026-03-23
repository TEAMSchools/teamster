# CLAUDE.md

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
- **Pull requests**: Squash merge. When opening a PR, use
  `.github/pull_request_template.md` as the body — fill in the relevant sections
  based on the changes.
- **GitHub issues**: Do not open issues proactively — ask first when something
  warrants one, then open it if confirmed. Use `gh issue create` (not the web
  UI). Label it with a
  [conventional commit type](https://www.conventionalcommits.org/en/v1.0.0/)
  (`feat`, `fix`, `docs`, `refactor`, `chore`, etc.), any related source systems
  (e.g., `adp`, `powerschool`, `deanslist`), and `dagster` and/or `dbt` when
  applicable.
- **Design specs**: After a spec is written and reviewed, follow this order:
  1. Open a GitHub issue (`gh issue create`)
  2. Create and link the branch
     (`gh issue develop <number> --name <branch> --checkout`)
  3. Commit the spec to that branch
  4. Push the branch

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
`.trunk/config/` for per-linter configuration files. A pre-commit hook runs
`trunk check` — if a commit is rejected, fix the reported issues and re-commit.

**SQL style**: Before writing, reviewing, or commenting on SQL, read
`.trunk/config/.sqlfluff`. Key enforced rules: BigQuery dialect, trailing commas
**required** in SELECT clauses, single quotes for literals, max line length 88.
Do not flag code that follows these rules.

**Shell style**: `shfmt` enforces tabs. Linter ignores use
`# trunk-ignore(shellcheck/SCXXXX)` with a reason comment, not
`# shellcheck disable=`.

### BigQuery MCP Queries

The BigQuery MCP tool truncates results at 50 rows. When querying
`INFORMATION_SCHEMA.COLUMNS` for tables with >50 columns, paginate with
`WHERE ordinal_position > N` to get all rows.

### Secrets

`permissions.deny` rules and hooks guard sensitive paths and content. Read
`.claude/hooks/CLAUDE.md` before editing hooks, deny rules, protected paths, or
`.claude/settings.json`. Regression tests: `bash tests/hooks/run_all.sh`.

## Codespace / GKE Setup Quirks

- `sudo` is removed at the end of `postCreate.sh` — tooling that needs root
  (`gcloud components install`, Helm) is installed during setup. To add new
  components, update `postCreate.sh` and rebuild the container
- Codespaces silently strips `--cap-add` from `runArgs` — do not attempt
  namespace-based sandboxing (bwrap, unshare). Hooks are the sole enforcement
  layer for path-based access control

## Architecture

**IMPORTANT — you MUST read the relevant CLAUDE.md files before doing any work:
reading, explaining, reviewing, or modifying code. Do NOT skip this step, even
if you think you can answer from source code alone.**

- **Dagster code** (reading or editing) → read `src/teamster/CLAUDE.md` first
- **dbt models** (reading or editing) → read `src/dbt/CLAUDE.md` first
- **Any subdirectory** → read that directory's CLAUDE.md first

These files contain conventions, antipatterns, and architectural decisions that
are not discoverable from source code.
