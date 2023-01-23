from dagster import AssetSelection, build_asset_reconciliation_sensor, sensor
from dagster._core.definitions.asset_reconciliation_sensor import (
    AssetReconciliationCursor,
    reconcile,
)

from teamster.kippcamden.powerschool.db import assets

ps_daily_assets_sensor = build_asset_reconciliation_sensor(
    asset_selection=AssetSelection.assets(*assets.ps_daily_assets),
    name="ps_daily_assets_sensor",
)

ps_misc_assets_sensor = build_asset_reconciliation_sensor(
    asset_selection=AssetSelection.assets(*assets.ps_misc_assets),
    name="ps_misc_assets_sensor",
)

ps_transactiondate_assets_sensor = build_asset_reconciliation_sensor(
    asset_selection=AssetSelection.assets(*assets.ps_transactiondate_assets),
    name="ps_transactiondate_assets_sensor",
)

ps_assignment_assets_sensor = build_asset_reconciliation_sensor(
    asset_selection=AssetSelection.assets(*assets.ps_assignment_assets),
    name="ps_assignment_assets_sensor",
)

ps_contacts_assets_sensor = build_asset_reconciliation_sensor(
    asset_selection=AssetSelection.assets(*assets.ps_contacts_assets),
    name="ps_contacts_assets_sensor",
)

ps_custom_assets_sensor = build_asset_reconciliation_sensor(
    asset_selection=AssetSelection.assets(*assets.ps_custom_assets),
    name="ps_custom_assets_sensor",
)

asset_selection = AssetSelection.assets(*assets.ps_assignment_assets)


@sensor(asset_selection=asset_selection, minimum_interval_seconds=3600)
def ps_incremental_sensor(context):
    cursor = (
        AssetReconciliationCursor.from_serialized(
            context.cursor, context.repository_def.asset_graph
        )
        if context.cursor
        else AssetReconciliationCursor.empty()
    )
    context.log.info(cursor)

    # run_requests, updated_cursor = reconcile(
    #     repository_def=context.repository_def,
    #     asset_selection=asset_selection,
    #     instance=context.instance,
    #     cursor=cursor,
    # )

    # context.update_cursor(updated_cursor.serialize())
    # return run_requests


__all__ = [
    ps_daily_assets_sensor,
    ps_assignment_assets_sensor,
    ps_custom_assets_sensor,
    ps_contacts_assets_sensor,
    ps_misc_assets_sensor,
    ps_transactiondate_assets_sensor,
    ps_incremental_sensor,
]
