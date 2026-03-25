# Design: dbt Extract YML Auto-Generation

**Date:** 2026-03-24 **Status:** Approved

## Problem

Every dbt extract model (`rpt_*` in `extracts/`) requires a matching `.yml`
property file with column names, data types, and a uniqueness test. Without it,
the model won't build because contract enforcement is enabled at the directory
level. Currently these YML files are created manually, which:

- Interrupts developer flow when adding new extract models
- Causes build failures when the YML is forgotten or incomplete
- Requires tedious column-by-column data type lookup from BigQuery

## Goals

- Automatically sync existing YML property files when extract SQL files are
  saved
- Generate complete YML files for new extract models on demand
- Block commits that introduce extract SQL files without complete YMLs
- Eliminate manual YML maintenance for the `extracts/` layer

## Non-Goals

- Auto-generation for non-extract models (staging, intermediate, marts)
- Replacing manual YML edits — the tool generates a starting point, developers
  refine descriptions and tests
- Running dbt builds or validating SQL correctness

## Architecture

Two event-driven components backed by a shared Python module:

1. **File watcher** (VS Code background task) — on SQL save, parses the SELECT
   columns and syncs the matching YML with BigQuery data types
2. **Pre-commit hook** (Trunk custom action) — blocks commits with missing or
   incomplete YMLs; prints generator/deferral instructions

### Shared module

All reusable logic lives in `.vscode/scripts/shared/dbt_yml_utils.py`:

| Function                 | Purpose                                                                             |
| ------------------------ | ----------------------------------------------------------------------------------- |
| `strip_jinja()`          | Remove Jinja/SQL comments, replace expressions with placeholder                     |
| `find_first_select()`    | Extract column body from first top-level SELECT (handles CTEs, UNION ALL, DISTINCT) |
| `parse_select_columns()` | Split SELECT body into ordered column names                                         |
| `find_yml_path()`        | Compute `properties/<model>.yml` path from SQL path                                 |
| `resolve_schema()`       | Read `dbt_project.yml` to resolve BigQuery dataset name                             |
| `query_column_types()`   | Query `INFORMATION_SCHEMA.COLUMNS` for data types                                   |
| `sync_yml()`             | Add/remove/reorder columns in YML, preserving metadata                              |

### Data flow

```text
SQL file saved
  -> strip_jinja() -> find_first_select() -> parse_select_columns()
  -> resolve_schema() -> query_column_types()
  -> sync_yml() (existing) or generate_yml() (new)
```

### Schema resolution

The BigQuery dataset is derived from `dbt_project.yml` `+schema` config:

| Project    | Path                | BQ dataset (prod)     |
| ---------- | ------------------- | --------------------- |
| kipptaf    | `extracts/`         | `kipptaf_extracts`    |
| kipptaf    | `extracts/tableau/` | `kipptaf_tableau`     |
| kippnewark | `extracts/`         | `kippnewark_extracts` |
| kippcamden | `extracts/`         | `kippcamden_extracts` |
| kippmiami  | `extracts/`         | `kippmiami_extracts`  |

## Components

### File watcher (`dbt-extracts-yml-sync.py`)

- Uses `watchdog` with `PatternMatchingEventHandler` on `*.sql`
- Watches all `src/dbt/*/models/extracts/` directories recursively
- Debounces with 1-second per-path window
- Only acts on files that already have a YML (new files deferred to commit time)
- Registered as auto-start VS Code background task (`runOn: folderOpen`)

### YML generator (`dbt-extracts-yml-generate.py`)

- CLI script: `uv run .vscode/scripts/dbt-extracts-yml-generate.py <sql_path>`
- Generates complete YML with `contract: enforced: true`, column list with data
  types, and a `dbt_utils.unique_combination_of_columns` stub
- Supports deferral: `--defer [--defer-for=N]` to skip the pre-commit check

### Pre-commit hook (`dbt-extracts-yml-check.sh`)

- Trunk custom action triggered on `pre-commit`
- For new SQL files: blocks if no matching YML, or if YML is incomplete (missing
  `data_type:` or uniqueness test)
- For modified SQL files: prints non-blocking downstream impact reminder
- Respects deferrals stored in `.vscode/.yml-sync-deferrals.json`

## Generated YML format

```yaml
models:
  - name: rpt_clever__enrollments
    config:
      contract:
        enforced: true
    description: "TODO: set the correct unique key columns in data_tests below"
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - school_id
              - section_id
          config:
            store_failures: true
    columns:
      - name: school_id
        data_type: int64
      - name: section_id
        data_type: string
      - name: student_id
        data_type: int64
```

## File map

| File                                           | Action          |
| ---------------------------------------------- | --------------- |
| `.vscode/scripts/shared/__init__.py`           | Create          |
| `.vscode/scripts/shared/dbt_yml_utils.py`      | Create          |
| `tests/test_dbt_yml_utils.py`                  | Create          |
| `.vscode/scripts/dbt-extracts-yml-sync.py`     | Create          |
| `.vscode/scripts/dbt-extracts-yml-generate.py` | Create          |
| `.vscode/scripts/dbt-extracts-yml-check.sh`    | Create          |
| `.trunk/trunk.yaml`                            | Modify (manual) |
| `.vscode/tasks.json`                           | Modify          |
| `.vscode/CLAUDE.md`                            | Modify          |
| `src/dbt/CLAUDE.md`                            | Modify          |

## Testing

- 42 unit tests in `tests/test_dbt_yml_utils.py` covering all shared functions
- Integration tests against real SQL files (`rpt_clever__enrollments.sql`) and
  real `dbt_project.yml` schema resolution
- Mocked BigQuery client for `query_column_types` tests
- Smoke test: watcher initializes and discovers all extracts directories

## Manual steps required

After merge, a developer must manually add the Trunk action definition to
`.trunk/trunk.yaml` (protected by hooks):

```yaml
actions:
  definitions:
    - id: dbt-extract-yml-check
      display_name: dbt Extract YML Check
      description:
        Ensures staged extract SQL files have complete YML property files
      run: bash .vscode/scripts/dbt-extracts-yml-check.sh
      triggers:
        - git_hooks: [pre-commit]
  enabled:
    - dbt-extract-yml-check
    - trunk-announce
    - trunk-check-pre-push
    - trunk-fmt-pre-commit
    - trunk-upgrade-available
```

## Risks and mitigations

| Risk                                | Mitigation                                                                    |
| ----------------------------------- | ----------------------------------------------------------------------------- |
| BigQuery unreachable                | `query_column_types` returns `{}` on error; columns added without `data_type` |
| SQL too complex to parse            | `find_first_select` raises `ValueError`; watcher logs and skips               |
| Multi-model YML files               | `sync_yml` warns to stderr, processes only first model                        |
| SQL injection via crafted filenames | `dataset`/`project` validated with regex; `table_name` parameterized          |
