from teamster.core.powerschool.sensors import build_partition_sensor

from .. import CODE_LOCATION, LOCAL_TIMEZONE
from .assets import partition_assets

partition_sensor = build_partition_sensor(
    name=f"{CODE_LOCATION}_powerschool_partition_sensor",
    asset_defs=partition_assets,
    timezone=LOCAL_TIMEZONE,
    minimum_interval_seconds=(60 * 60),
)

__all__ = [
    partition_sensor,
]
