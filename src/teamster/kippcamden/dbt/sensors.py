from dagster import AssetSelection, build_asset_reconciliation_sensor

from . import assets

dbt_powerschool_asset_reconciliation_sensor = build_asset_reconciliation_sensor(
    asset_selection=AssetSelection.assets(
        *assets.powerschool_src_assets,
        *assets.powerschool_nonpartition_stg_assets,
        *assets.powerschool_incremental_stg_assets,
    ),
    name="dbt_powerschool_asset_sensor",
)

__all__ = [
    dbt_powerschool_asset_reconciliation_sensor,
]
