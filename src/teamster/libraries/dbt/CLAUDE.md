# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Core library for wrapping dbt projects as Dagster assets. Every code location's
`dbt/assets.py` calls `build_dbt_assets()` from here.

## Files

### `assets.py` — `build_dbt_assets()`

Wraps `@dbt_assets` with two additional behaviors before running `dbt build`:

1. **External source staging**: Inspects the manifest for `external` sources
   upstream of the selected assets, then runs
   `dbt run-operation stage_external_sources` to create/refresh BigLake external
   tables in BigQuery.
2. **BigLake metadata refresh**: For external sources using a BigLake
   `connection_name`, runs `dbt run-operation refresh_external_metadata_cache`.

This means adding a new external source to a dbt project automatically triggers
staging without any Dagster code changes.

### `dagster_dbt_translator.py` — `CustomDagsterDbtTranslator`

Customizes asset key and automation condition generation:

- **Asset keys**: Prefixes all keys with `code_location` (e.g.,
  `kippnewark/powerschool/stg_powerschool__students`) unless the model's
  `meta.dagster.asset_key` is already set.
- **Automation condition**: A forked version of `AutomationCondition.eager()`
  that also triggers on `code_version_changed()`, ignores external source assets
  from dep-missing checks, and allows initial evaluation. Views using
  `union_relations` are auto-detected (via `raw_code` inspection) and assigned
  `dbt_union_relations_automation_condition()` — a third condition that adds
  recursive ancestor `code_version_changed` detection (but not
  `any_deps_updated`) to the view condition. This re-runs the view only when
  upstream model SQL changes after a deploy, not on data-only refreshes. The
  condition type can also be overridden manually via
  `meta.dagster.automation_condition.type: table|view`.
- **Group name**: Falls back to the dbt package name (for cross-project refs)
  then the first FQN segment after the project name.

### `schedules.py` — `build_dbt_code_version_schedule()`

Produces a schedule that runs only the dbt assets whose compiled SQL has changed
since their last materialization (compares `code_versions_by_key` against
`get_latest_materialization_code_versions`).

> **Note**: `dbt_code_version_schedule` was previously defined in
> `dbt/schedules.py` for `kippnewark`, `kippcamden`, and `kippmiami` but was
> never wired into any `definitions.py` and has since been deleted.
