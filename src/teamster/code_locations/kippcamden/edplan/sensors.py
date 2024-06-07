from teamster.code_locations.kippcamden import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippcamden.edplan import assets
from teamster.libraries.edplan.sensors import build_sftp_sensor

sftp_sensor = build_sftp_sensor(
    sensor_name=f"{CODE_LOCATION}_edplan_sftp_sensor",
    asset_defs=assets,
    timezone=LOCAL_TIMEZONE,
    minimum_interval_seconds=(60 * 10),
)

sensors = [
    sftp_sensor,
]
