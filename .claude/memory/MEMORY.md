# Teamster Project Memory

## dbt Asset Automation Conditions & Unsynced Badge

The project uses two custom `AutomationCondition` builders in
`src/teamster/core/automation_conditions.py`:

- `dbt_view_automation_condition()` — triggers only on `newly_missing`,
  `code_version_changed`, or `execution_failed`. Intentionally omits
  `any_deps_updated` since views are computed on read.
- `dbt_table_automation_condition()` — triggers on upstream data changes
  (including through intermediate views via recursive `any_deps_match`), plus
  `code_version_changed`.

**Unsynced badge behavior**: Dagster's "unsynced" indicator is driven by its
**data versioning system**, not the automation condition. When an upstream table
materializes, directly-dependent view assets are marked "unsynced" in the UI
even though the automation condition correctly suppresses any run. There is no
built-in Dagster API to suppress this per-asset.

**Open issue**: [#3397](https://github.com/TEAMSchools/teamster/issues/3397) —
Emit `AssetObservation` events with a stable `DataVersion` (SQL hash) for view
assets at the end of table runs in `build_dbt_assets`. Since it's a multi-asset,
both tables and views are in the same function — no coupling issue. No
additional credit cost since observations are emitted within the already-running
step.

## User Preferences

- When requesting permission to run a command, provide a brief plain-language
  summary of what the command will do. Include a table of commands that will be
  executed and files that will be touched.
- Save all memory to the project directory (.claude/memory/) when operating
  within a devcontainer.
