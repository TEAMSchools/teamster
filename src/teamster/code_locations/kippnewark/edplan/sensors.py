from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.edplan.assets import njsmart_powerschool
from teamster.libraries.edplan.sensors import build_edplan_sftp_sensor

sftp_sensor = build_edplan_sftp_sensor(
    asset=njsmart_powerschool,
    code_location=CODE_LOCATION,
    execution_timezone=LOCAL_TIMEZONE,
    minimum_interval_seconds=(60 * 10),
)

sensors = [
    sftp_sensor,
]
