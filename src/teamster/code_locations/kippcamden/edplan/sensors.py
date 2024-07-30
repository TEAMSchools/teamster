from teamster.code_locations.kippcamden import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippcamden.edplan.assets import njsmart_powerschool
from teamster.libraries.edplan.sensors import build_edplan_sftp_sensor

sftp_sensor = build_edplan_sftp_sensor(
    code_location=CODE_LOCATION,
    asset=njsmart_powerschool,
    timezone=LOCAL_TIMEZONE,
    minimum_interval_seconds=(60 * 10),
)

sensors = [
    sftp_sensor,
]
