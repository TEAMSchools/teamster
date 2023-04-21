from dagster import AssetSelection, build_asset_reconciliation_sensor

from .. import CODE_LOCATION
from .assets import dbt_src_assets

asset_reconciliation_sensor = build_asset_reconciliation_sensor(
    asset_selection=AssetSelection.assets(*dbt_src_assets),
    name=f"{CODE_LOCATION}_dbt_asset_reconciliation_sensor",
)

__all__ = [
    asset_reconciliation_sensor,
]
