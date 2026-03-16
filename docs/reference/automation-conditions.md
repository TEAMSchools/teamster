# Automation Conditions

Teamster uses two custom `AutomationCondition` builders in
`teamster.core.automation_conditions` that replace Dagster's default
`AutomationCondition.eager()` for dbt assets.

## VIEW vs TABLE

The core distinction is that **views are computed on read** — materializing a
view when upstream data changes just re-executes the same SQL against
already-updated data, so re-triggering on upstream changes is redundant.

### `dbt_view_automation_condition()`

For `materialized: view` dbt models. Triggers when:

- The asset is **newly missing** (e.g. first run, or dropped in BigQuery)
- The **compiled SQL has changed** (`code_version_changed`) — a dbt code deploy
- The **previous run failed**

`any_deps_updated` is intentionally omitted. When an upstream table
materializes, view assets correctly do not re-run.

### `dbt_table_automation_condition()`

For `materialized: table` models. Triggers on everything above, plus:

- **Upstream data changes** — including changes propagated through intermediate
  view chains (up to 10 levels deep via recursive dependency traversal)

The recursive traversal means a table asset will re-run when any upstream table
materializes, even if the direct dependency is a chain of views.

## Non-dbt partitioned assets

Non-dbt assets (e.g., BigQuery→SFTP extracts) use `AutomationCondition.eager()`
directly when they need reactive triggering. Two important behaviors when a
partitioned asset has mixed dep types:

- **Partitioned dep** (same `PartitionsDefinition`): updating partition `X`
  triggers only partition `X` of the downstream asset.
- **Non-partitioned dep**: any update fans out to **all** partitions of the
  downstream asset.

This means wiring a non-partitioned lookup table as a dep is intentional but has
cost — every refresh of that table triggers a full re-extract across all
partitions. Design accordingly.

## The "Unsynced" indicator

When an upstream table materializes, directly-dependent view assets show as
**Unsynced** in the Dagster UI. This is driven by Dagster's internal data
versioning system, not the automation condition.

The automation condition correctly suppresses any run trigger for view assets,
but there is no Dagster API to suppress the UI indicator on a per-asset basis.

**This is expected behavior, not a misconfiguration.** Unsynced views will clear
on their next scheduled or code-version-triggered materialization.
