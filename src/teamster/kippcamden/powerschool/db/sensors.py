from dagster import AssetSelection, build_asset_reconciliation_sensor

from teamster.core.powerschool.db.sensors import build_powerschool_incremental_sensor
from teamster.kippcamden.powerschool.db import assets

ps_incremental_sensor = build_powerschool_incremental_sensor(
    name="ps_incremental_sensor",
    asset_selection=AssetSelection.assets(*assets.ps_transactiondate_assets),
    where_col="transaction_date",
)

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

__all__ = [
    ps_daily_assets_sensor,
    ps_assignment_assets_sensor,
    ps_custom_assets_sensor,
    ps_contacts_assets_sensor,
    ps_misc_assets_sensor,
    ps_transactiondate_assets_sensor,
    ps_incremental_sensor,
]
