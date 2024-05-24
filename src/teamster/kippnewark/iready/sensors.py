from teamster.iready.sensors import build_iready_sftp_sensor
from teamster.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.kippnewark.iready import assets

sftp_sensor = build_iready_sftp_sensor(
    code_location=CODE_LOCATION,
    asset_defs=assets,
    timezone=LOCAL_TIMEZONE,
    remote_dir="/exports/nj-kipp_nj",
    minimum_interval_seconds=(60 * 10),
)

sensors = [
    sftp_sensor,
]
