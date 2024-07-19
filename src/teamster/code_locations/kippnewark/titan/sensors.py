from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.titan.assets import (
    income_form_data,
    person_data,
)
from teamster.libraries.titan.sensors import build_titan_sftp_sensor

sftp_sensor = build_titan_sftp_sensor(
    code_location=CODE_LOCATION,
    asset_selection=[income_form_data, person_data],
    timezone=LOCAL_TIMEZONE,
    minimum_interval_seconds=(60 * 10),
    exclude_dirs=["Scipt", "Script"],
)

sensors = [
    sftp_sensor,
]
