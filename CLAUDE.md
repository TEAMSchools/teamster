# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Project Overview

Teamster is a data engineering platform for KIPP TEAM & Family Schools (Newark,
Camden, and Paterson, NJ & Miami, FL) built on **Dagster** (orchestration),
**dbt** (transformations), and **Google BigQuery** (warehouse), with Google
Cloud Storage (GCS) as the intermediate storage layer.

## Skills

This project has specialized skills that provide deep framework knowledge.
Always use them before doing relevant work:

- **`/dagster-expert`** — Use before any Dagster task: creating assets,
  schedules, sensors, resources, debugging pipeline issues, or understanding
  definitions
- **`/dbt:using-dbt-for-analytics-engineering`** — Use when building or
  modifying dbt models, writing tests, or debugging dbt errors
- **`/dbt:running-dbt-commands`** — Use when running dbt CLI commands
- **`/dbt:adding-dbt-unit-test`** — Use when adding unit tests for a dbt model
- **`/dbt:troubleshooting-dbt-job-errors`** — Use when diagnosing dbt job
  failures or unclear error messages
- **`/dbt:fetching-dbt-docs`** — Use when looking up dbt features or
  documentation
- **`/dignified-python`** + **`/simplify`** — Run together after substantial
  Python changes to enforce production quality standards and review for reuse,
  quality, and efficiency. Skip for minor or isolated edits.

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

Linting is managed via [Trunk](https://trunk.io). Configuration lives in
`.trunk/trunk.yaml` (enabled linters) and `.trunk/config/` (per-linter config
files).

Enabled linters:

| Linter           | Config file                        | Scope                        |
| ---------------- | ---------------------------------- | ---------------------------- |
| `ruff`           | `.trunk/config/ruff.toml`          | Python (`src/teamster/`)     |
| `pyright`        | `.trunk/config/pyrightconfig.json` | Python (excl. `dlt_sources`) |
| `isort`          | `.trunk/config/.isort.cfg`         | Python                       |
| `bandit`         | `.trunk/config/.bandit`            | Python                       |
| `sqlfluff`       | `.trunk/config/.sqlfluff`          | SQL (`src/dbt/`)             |
| `sqlfmt`         | —                                  | SQL (`src/dbt/`)             |
| `prettier`       | `.trunk/config/.prettierrc.yaml`   | YAML, JSON, Markdown, etc.   |
| `yamllint`       | `.trunk/config/.yamllint`          | YAML                         |
| `markdownlint`   | `.trunk/config/.markdownlint.yaml` | Markdown                     |
| `hadolint`       | `.trunk/config/.hadolint.yaml`     | Dockerfiles                  |
| `shellcheck`     | `.trunk/config/.shellcheckrc`      | Shell scripts                |
| `shfmt`          | —                                  | Shell scripts                |
| `actionlint`     | —                                  | GitHub Actions workflows     |
| `taplo`          | —                                  | TOML                         |
| `gitleaks`       | —                                  | Secrets scanning             |
| `osv-scanner`    | —                                  | Dependency vulnerabilities   |
| `oxipng`         | —                                  | PNG optimization             |
| `svgo`           | `.trunk/config/svgo.config.js`     | SVG optimization             |
| `git-diff-check` | —                                  | Merge conflict markers       |

```bash
# Check all files
trunk check

# Auto-format all files
trunk fmt
```

**SQL style**: Before writing, reviewing, or commenting on SQL, read
`.trunk/config/.sqlfluff`. Key enforced rules: BigQuery dialect, trailing commas
**required** in SELECT clauses, single quotes for literals, max line length 88.
Do not flag code that follows these rules.

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

### Repository Structure

Each code location and library directory contains its own `CLAUDE.md` with
context specific to that module (active integrations, resource instances, asset
groups, etc.). Read the relevant `CLAUDE.md` before working in a specific code
location or library.

```text
src/
  teamster/               # Dagster project (Python package)
    __init__.py           # GCS_PROJECT_NAME constant
    core/                 # Shared infrastructure (CLAUDE.md)
      resources.py        # Shared resource instances (BigQuery, GCS, SSH, dbt, IO managers)
      io_managers/        # Custom GCS IO managers (pickle, avro, file)
      utils/              # Utility classes (FiscalYear, partitions, JSON encoder)
    libraries/            # Reusable asset builders and resource definitions
      adp/                # ADP Workforce Now + WFM (CLAUDE.md)
      airbyte/            # Airbyte Cloud (CLAUDE.md)
      alchemer/           # Alchemer survey API (CLAUDE.md)
      amplify/            # Amplify reading platform (CLAUDE.md)
      collegeboard/       # College Board SFTP (CLAUDE.md)
      couchdrop/          # CouchDrop SFTP sensor (CLAUDE.md)
      coupa/              # Coupa procurement API (CLAUDE.md)
      dayforce/           # Dayforce HCM (CLAUDE.md)
      dbt/                # dbt asset builder: build_dbt_assets (CLAUDE.md)
      deanslist/          # Deanslist API (CLAUDE.md)
      dlt/                # DLT pipeline assets (CLAUDE.md)
      edplan/             # EdPlan SFTP (CLAUDE.md)
      email/              # Email/SMTP (CLAUDE.md)
      extracts/           # BigQuery→SFTP extract assets (CLAUDE.md)
      finalsite/          # Finalsite CMS (CLAUDE.md)
      fivetran/           # Fivetran connectors (CLAUDE.md)
      fldoe/              # Florida DOE (CLAUDE.md)
      google/             # Google Drive, Forms, Sheets, Directory (CLAUDE.md)
      iready/             # iReady assessment platform (CLAUDE.md)
      knowbe4/            # KnowBe4 security training API (CLAUDE.md)
      ldap/               # LDAP directory (CLAUDE.md)
      level_data/         # LevelData Grow API (CLAUDE.md)
      nsc/                # National Student Clearinghouse SFTP (CLAUDE.md)
      overgrad/           # Overgrad college counseling API (CLAUDE.md)
      pearson/            # Pearson assessments (CLAUDE.md)
      performance_management/ # PM SFTP assets (CLAUDE.md)
      powerschool/        # PowerSchool SIS (ODBC via Oracle) and enrollment (CLAUDE.md)
      renlearn/           # Renaissance Learning (CLAUDE.md)
      sftp/               # Generic SFTP resource (CLAUDE.md)
      smartrecruiters/    # SmartRecruiters ATS API (CLAUDE.md)
      ssh/                # SSH tunnel resource (CLAUDE.md)
      tableau/            # Tableau Server (CLAUDE.md)
      titan/              # Titan school nutrition (CLAUDE.md)
      zendesk/            # Zendesk support platform (CLAUDE.md)
    code_locations/       # Per-school Dagster definitions
      kipptaf/            # TAF (network-wide): the largest code location (CLAUDE.md)
      kippnewark/         # (CLAUDE.md)
      kippcamden/         # (CLAUDE.md)
      kippmiami/          # (CLAUDE.md)
      kipppaterson/       # (CLAUDE.md)
  dbt/                    # dbt projects (one per data source or school network)
    kipptaf/              # Main network-wide dbt project (CLAUDE.md)
    kippnewark/           # School-specific dbt project
    kippcamden/
    kippmiami/
    kipppaterson/
    amplify/              # Source-system dbt projects
    deanslist/
    edplan/
    finalsite/
    iready/
    overgrad/
    pearson/
    powerschool/
    renlearn/
    titan/
```

### Key Architectural Patterns

**Subdirectory naming convention**: Within a code location, subdirectory names
signal the type of integration:

- `dbt/`, `dlt/`, `google/` — framework-integrated modules (Dagster-native
  integrations with lifecycle managed by a Dagster library, e.g. `dagster-dbt`,
  `dagster-dlt`)
- `powerschool/`, `deanslist/`, etc. — direct integrations (custom asset
  builders in `src/teamster/libraries/`)

**Code Location Pattern**: Each school network has a `code_locations/<name>/`
directory with:

- `CLAUDE.md` — module-specific context (active integrations, resources, asset
  groups); read this before working in a code location
- `__init__.py` — defines `CODE_LOCATION`, `LOCAL_TIMEZONE`,
  `CURRENT_FISCAL_YEAR`, `DBT_PROJECT`
- `definitions.py` — the `Definitions` object wiring all assets, schedules,
  sensors, resources
- `resources.py` — code-location-specific resource instances
- `dbt/` — dbt asset definitions (loads manifest, builds `dbt_assets`)
- `dlt/` — DLT pipeline assets
- `google/` — Google Workspace assets
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

- Models follow `stg_` (staging), `int_` (intermediate), `rpt_` (reporting views
  / extracts), `dim_*` / `fct_*` (data mart) prefixes
- `src/dbt/kipptaf/` is the primary analytics project; school-specific projects
  (`kippnewark`, etc.) contain school-specific extracts
- dbt packages are vendored into `dbt_packages/` subdirectories within each
  project
- Fiscal year starts July 1; `current_academic_year` and `current_fiscal_year`
  vars are set in `dbt_project.yml`

For model quality requirements (contract enforcement, uniqueness tests, SQL
antipatterns), see `src/dbt/CLAUDE.md`. For kipptaf-specific inherited defaults
and exposure YAML reference, see `src/dbt/kipptaf/CLAUDE.md`.

**Exposures**: Every external tool consuming data from a dbt project must have a
dbt exposure in that project's `models/exposures/` directory listing all
`depends_on` models. School-specific projects (`kippnewark`, `kippcamden`,
`kippmiami`) require exposures for their PowerSchool extracts.
