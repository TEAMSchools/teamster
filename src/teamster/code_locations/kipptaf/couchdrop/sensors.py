from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.performance_management.assets import (
    observation_details,
)
from teamster.code_locations.kipptaf.tableau.assets import traffic_to_views
from teamster.libraries.couchdrop.sensors import build_couchdrop_sftp_sensor

couchdrop_sftp_sensor = build_couchdrop_sftp_sensor(
    code_location=CODE_LOCATION,
    local_timezone=LOCAL_TIMEZONE,
    asset_selection=[observation_details, traffic_to_views],
    minimum_interval_seconds=(60 * 10),
    exclude_dirs=[
        "/data-team/kipptaf/dayforce",
        "/data-team/kipptaf/njdoe",
        "/data-team/kipptaf/performance-management",
        "/data-team/kipptaf/surveys",
    ],
)

sensors = [
    couchdrop_sftp_sensor,
]
