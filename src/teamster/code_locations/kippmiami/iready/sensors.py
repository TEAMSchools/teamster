from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.iready import assets
from teamster.libraries.iready.sensors import build_iready_sftp_sensor

sftp_sensor = build_iready_sftp_sensor(
    code_location=CODE_LOCATION,
    asset_defs=assets,
    timezone=LOCAL_TIMEZONE,
    remote_dir="/exports/fl-kipp_miami",
    minimum_interval_seconds=(60 * 10),
)

sensors = [
    sftp_sensor,
]
