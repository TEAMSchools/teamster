from teamster.code_locations.kippcamden import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippcamden.powerschool.assets import (
    dcid_assets,
    partition_assets,
)
from teamster.libraries.powerschool.sis.sensors import build_powerschool_sensor

partition_sensor = build_powerschool_sensor(
    name=f"{CODE_LOCATION}_powerschool_partition_sensor",
    asset_selection=[*dcid_assets, *partition_assets],
    asset_defs=partition_assets,
    execution_timezone=LOCAL_TIMEZONE,
    minimum_interval_seconds=(60 * 10),
    max_runtime_seconds=(60 * 6),
)

sensors = [
    partition_sensor,
]
