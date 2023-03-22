from teamster.core.powerschool.sensors import build_dynamic_partition_sensor

from .. import CODE_LOCATION
from . import assets

powerschool_dynamic_partition_sensor = build_dynamic_partition_sensor(
    code_location=CODE_LOCATION,
    name="powerschool_dynamic_partition_sensor",
    assets=[*assets.partition_assets],
    minimum_interval_seconds=900,
)

__all__ = [
    powerschool_dynamic_partition_sensor,
]
