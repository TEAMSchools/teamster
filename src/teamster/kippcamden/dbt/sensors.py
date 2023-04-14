from dagster import AssetSelection, build_asset_reconciliation_sensor

from .. import CODE_LOCATION
from . import assets

powerschool_dbt_src_asset_reconciliation_sensor = build_asset_reconciliation_sensor(
    asset_selection=AssetSelection.assets(*assets.powerschool_dbt_src_assets),
    name=f"{CODE_LOCATION}_powerschool_dbt_src_asset_reconciliation_sensor",
)

powerschool_dbt_stg_asset_reconciliation_sensor = build_asset_reconciliation_sensor(
    asset_selection=AssetSelection.assets(*assets.powerschool_dbt_stg_assets),
    name=f"{CODE_LOCATION}_powerschool_dbt_stg_asset_reconciliation_sensor",
)

deanslist_dbt_src_asset_reconciliation_sensor = build_asset_reconciliation_sensor(
    asset_selection=AssetSelection.assets(*assets.deanslist_dbt_src_assets),
    name=f"{CODE_LOCATION}_deanslist_dbt_src_asset_reconciliation_sensor",
)

__all__ = [
    powerschool_dbt_src_asset_reconciliation_sensor,
    powerschool_dbt_stg_asset_reconciliation_sensor,
    deanslist_dbt_src_asset_reconciliation_sensor,
]
