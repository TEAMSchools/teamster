from teamster.core.edplan.sensors import build_sftp_sensor

from .. import CODE_LOCATION, LOCAL_TIMEZONE
from . import assets

sftp_sensor = build_sftp_sensor(
    sensor_name=f"{CODE_LOCATION}_edplan_sftp_sensor",
    asset_defs=assets,
    timezone=LOCAL_TIMEZONE,
    minimum_interval_seconds=(60 * 10),
)

_all = [
    sftp_sensor,
]
