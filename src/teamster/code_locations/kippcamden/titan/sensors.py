from teamster.code_locations.kippcamden import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippcamden.titan.assets import person_data
from teamster.libraries.titan.sensors import build_titan_sftp_sensor

titan_sftp_sensor = build_titan_sftp_sensor(
    code_location=CODE_LOCATION,
    asset_selection=[person_data],
    timezone=LOCAL_TIMEZONE,
    minimum_interval_seconds=(60 * 30),
    exclude_dirs=["Scipt", "Script"],
)

sensors = [
    titan_sftp_sensor,
]
