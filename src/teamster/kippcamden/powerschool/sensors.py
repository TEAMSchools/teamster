from dagster import AssetSelection

from teamster.core.powerschool.sensors import build_dynamic_partition_sensor

from .. import CODE_LOCATION
from . import assets

powerschool_dynamic_partition_sensor = build_dynamic_partition_sensor(
    code_location=CODE_LOCATION,
    name="powerschool_dynamic_partition_sensor",
    asset_selection=AssetSelection.assets(*assets.partition_assets),
    partitions_def=assets.dynamic_partitions_def,
    minimum_interval_seconds=900,
)

__all__ = [
    powerschool_dynamic_partition_sensor,
]
