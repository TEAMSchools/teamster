from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.edplan.assets import (
    njsmart_powerschool,
    section_504_student_report,
)
from teamster.libraries.edplan.sensors import build_edplan_sftp_sensor

sftp_sensor = build_edplan_sftp_sensor(
    assets=[njsmart_powerschool, section_504_student_report],
    code_location=CODE_LOCATION,
    execution_timezone=LOCAL_TIMEZONE,
    minimum_interval_seconds=(60 * 10),
)

sensors = [
    sftp_sensor,
]
