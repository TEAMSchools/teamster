# Automation Conditions

Teamster uses three custom `AutomationCondition` builders in
`teamster.core.automation_conditions` that replace Dagster's default
`AutomationCondition.eager()` for dbt assets. All three share a common skeleton
(`_build_dbt_condition`) and differ only in what triggers a materialization
request beyond `newly_missing`.

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

## `union_relations` views

Views that use the `union_relations` macro are a special case. Unlike regular
views, their compiled SQL resolves column lists at run time — the macro expands
upstream table columns into an explicit `SELECT` with `UNION ALL`. If an
upstream regional table adds or removes a column and the view is not re-run, its
compiled SQL becomes stale.

Importantly, `code_version_changed` does **not** catch this. Dagster derives
`code_version` from a SHA1 of the model's `raw_code` (the Jinja source), not the
compiled SQL. When the `union_relations` macro produces different output because
upstream schemas changed, the raw source file hasn't changed, so the code
version stays the same.

### `dbt_union_relations_automation_condition()`

A third condition that sits between view and table. Triggers on everything in
the view condition, plus:

- **Ancestor code version changes** — recursive `code_version_changed` detection
  through intermediate views (up to 10 levels). When an upstream model's raw SQL
  changes (e.g., a staging model adds a column after a deploy), the view re-runs
  so the `union_relations` macro recompiles with the updated column set.

Unlike the table condition, this does **not** trigger on upstream data changes
(`any_deps_updated`). Re-materializing views on every upstream data refresh
would waste Dagster credits and Kubernetes resources. Only code deploys that
change upstream model definitions trigger a re-run.

The `CustomDagsterDbtTranslator` **auto-detects** these views by checking for
`"union_relations"` in the model's `raw_code`.

To manually override the condition type for any model, set
`meta.dagster.automation_condition.type` in the dbt model's config:

```yaml
models:
  - name: my_model
    config:
      meta:
        dagster:
          automation_condition:
            type: table # or "view"
```

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
