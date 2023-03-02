from dagster import AssetSelection

from teamster.core.powerschool.db.sensors import build_dynamic_parition_sensor
from teamster.kippcamden.powerschool.db import assets

test_dynamic_partition_sensor = build_dynamic_parition_sensor(
    name="test_dynamic_partition_sensor",
    asset_selection=AssetSelection.assets(*assets.partition_assets),
)

__all__ = [test_dynamic_partition_sensor]
