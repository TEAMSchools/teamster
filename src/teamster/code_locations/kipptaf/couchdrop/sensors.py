from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.performance_management.assets import (
    observation_details,
)
from teamster.libraries.couchdrop.sensors import build_couchdrop_sftp_sensor

couchdrop_sftp_sensor = build_couchdrop_sftp_sensor(
    code_location=CODE_LOCATION,
    local_timezone=LOCAL_TIMEZONE,
    asset_selection=[observation_details],
    minimum_interval_seconds=(60 * 10),
    exclude_dirs=[
        f"/data-team/{CODE_LOCATION}/surveys",
        f"/data-team/{CODE_LOCATION}/dayforce",
        f"/data-team/{CODE_LOCATION}/performance-management",
    ],
)

sensors = [
    couchdrop_sftp_sensor,
]
