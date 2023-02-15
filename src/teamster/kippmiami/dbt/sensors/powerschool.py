from dagster import AssetSelection, build_asset_reconciliation_sensor

from teamster.kippmiami.dbt.assets import powerschool

asset_reconciliation_sensor = build_asset_reconciliation_sensor(
    asset_selection=AssetSelection.assets(*powerschool.src_assets),
    name="dbt_powerschool_asset_sensor",
)

__all__ = [asset_reconciliation_sensor]
