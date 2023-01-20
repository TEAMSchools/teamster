from dagster import AssetSelection, build_asset_reconciliation_sensor

from teamster.kippcamden.powerschool.db.assets import (
    ps_db_assets,
    ps_db_partitioned_assets,
)

ps_db_assets_sensor = build_asset_reconciliation_sensor(
    asset_selection=AssetSelection.assets(*ps_db_assets), name="ps_db_assets_sensor"
)

ps_db_partitioned_assets_sensor = build_asset_reconciliation_sensor(
    asset_selection=AssetSelection.assets(*ps_db_partitioned_assets),
    name="ps_db_partitioned_assets_sensor",
)

__all__ = [ps_db_assets_sensor, ps_db_partitioned_assets_sensor]
