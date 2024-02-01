from teamster.core.iready.sensors import build_iready_sftp_sensor

from .. import CODE_LOCATION, LOCAL_TIMEZONE
from . import assets

sftp_sensor = build_iready_sftp_sensor(
    code_location=CODE_LOCATION,
    asset_defs=assets,
    timezone=LOCAL_TIMEZONE,
    remote_dir="/exports/fl-kipp_miami",
    minimum_interval_seconds=(60 * 10),
)

_all = [
    sftp_sensor,
]
