# CLAUDE.md — `teamster/libraries/tableau/`

Dagster asset factory and resource for **Tableau Server** workbook refresh.
Assets represent Tableau workbooks that are refreshed after upstream dbt models
complete.

## Factory: `build_tableau_workbook_refresh_asset()`

Produces an asset that:

1. Declares upstream `deps` from `get_asset_key_for_model()` (referencing
   `core_dbt_assets` from `kipptaf.dbt`)
2. Calls `tableau._server.workbooks.get_by_id()` to fetch the workbook, then
   `tableau._server.workbooks.refresh()` to trigger the refresh
3. Uses the `tableau_pat_session_limit` pool to prevent concurrent PAT session
   exhaustion

**Important**: This factory imports directly from
`teamster.code_locations.kipptaf.dbt.assets` — it is tightly coupled to the
`kipptaf` code location and cannot be used for other code locations.

Asset metadata, kinds, and label come from the workbook's dbt
`config.meta.dagster` block.

## Resource: `TableauServerResource`

Authenticates to Tableau Server via Personal Access Token (PAT). Exposes
`_server` (a `tableauserverclient.Server` instance) for workbook operations.
