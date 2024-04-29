from teamster.core.powerschool.sensors import build_powerschool_sensor

from .. import CODE_LOCATION, LOCAL_TIMEZONE
from .assets import dcid_assets, partition_assets

partition_sensor = build_powerschool_sensor(
    name=f"{CODE_LOCATION}_powerschool_partition_sensor",
    asset_selection=[*dcid_assets, *partition_assets],
    asset_defs=partition_assets,
    execution_timezone=LOCAL_TIMEZONE,
    minimum_interval_seconds=(60 * 10),
    max_runtime_seconds=(60 * 7),
)

_all = [
    partition_sensor,
]
