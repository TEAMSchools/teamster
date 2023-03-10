from dagster import AssetSelection, build_asset_reconciliation_sensor

from . import assets

dbt_asset_reconciliation_sensor = build_asset_reconciliation_sensor(
    asset_selection=AssetSelection.assets(*assets.__all__),
    name="dbt_asset_reconciliation_sensor",
)

__all__ = [
    dbt_asset_reconciliation_sensor,
]
