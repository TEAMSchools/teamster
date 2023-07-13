from teamster.core.powerschool.sensors import build_dynamic_partition_sensor

from .. import CODE_LOCATION, LOCAL_TIMEZONE
from .assets import partition_assets

powerschool_dynamic_partition_sensor = build_dynamic_partition_sensor(
    code_location=CODE_LOCATION,
    name=f"{CODE_LOCATION}_powerschool_dynamic_partition_sensor",
    asset_defs=partition_assets,
    timezone=LOCAL_TIMEZONE,
    minimum_interval_seconds=(60 * 60),
)

__all__ = [
    powerschool_dynamic_partition_sensor,
]
