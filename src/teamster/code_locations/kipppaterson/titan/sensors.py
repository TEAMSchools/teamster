from teamster.code_locations.kipppaterson import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipppaterson.titan.assets import person_data
from teamster.libraries.titan.sensors import build_titan_sftp_sensor

titan_sftp_sensor = build_titan_sftp_sensor(
    code_location=CODE_LOCATION,
    asset_selection=[person_data],
    timezone=LOCAL_TIMEZONE,
    minimum_interval_seconds=(60 * 10),
    exclude_dirs=["Script"],
)

sensors = [
    titan_sftp_sensor,
]
