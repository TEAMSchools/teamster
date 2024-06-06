from teamster.code_locations.kippcamden import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippcamden.titan import assets
from teamster.libraries.titan.sensors import build_titan_sftp_sensor

sftp_sensor = build_titan_sftp_sensor(
    code_location=CODE_LOCATION,
    asset_defs=assets,
    timezone=LOCAL_TIMEZONE,
    minimum_interval_seconds=(60 * 10),
)

sensors = [
    sftp_sensor,
]
