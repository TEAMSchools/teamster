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

### BigQuery MCP Queries

The BigQuery MCP tool truncates results at 50 rows. When querying
`INFORMATION_SCHEMA.COLUMNS` for tables with >50 columns, paginate with
`WHERE ordinal_position > N` to get all rows.

### Secrets

A PreToolUse hook (`.claude/hooks/check-sensitive.sh`) blocks access to
sensitive paths across Read/Edit/Write/Bash/Grep/Glob. Blocked patterns include:
`.env`, `.ssh`, `.pem`, `.key`, `.cer`, `env/`, `secret-volume`,
`.devcontainer/tpl/`, `.devcontainer/scripts/`, `*.cer`/`*.key`/`*.pem` globs,
`printenv`/`declare -x`/`set`/`compgen`/`/proc/*/environ`,
`op vault/item/read/document/inject`, and `OP_SERVICE_ACCOUNT_TOKEN` substrings
(`OP_SERVICE`, `ACCOUNT_TOKEN`). The hook is self-protecting — it also blocks
modifications to `.claude/settings.json` and `.claude/hooks/`. A `SessionStart`
hook scrubs `OP_SERVICE_ACCOUNT_TOKEN` from shell snapshots. MCP servers fetch
secrets via `op read`.

When testing the hook itself, write a temporary shell script to a non-protected
path and run it — inline Bash commands containing sensitive path strings will be
blocked by the hook.

To modify secret-handling scripts (`.devcontainer/scripts/`), draft the changes
and present them to the user for manual application — the hook blocks all AI
tool access to these files.

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

**IMPORTANT — you MUST read the relevant CLAUDE.md files before doing any work:
reading, explaining, reviewing, or modifying code. Do NOT skip this step, even
if you think you can answer from source code alone.**

- **Dagster code** (reading or editing) → read `src/teamster/CLAUDE.md` first
- **dbt models** (reading or editing) → read `src/dbt/CLAUDE.md` first
- **Any subdirectory** → read that directory's CLAUDE.md first

These files contain conventions, antipatterns, and architectural decisions that
are not discoverable from source code.
