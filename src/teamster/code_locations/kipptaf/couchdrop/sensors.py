from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.collegeboard.assets import psat
from teamster.code_locations.kipptaf.tableau.assets import view_count_per_view
from teamster.libraries.couchdrop.sensors import build_couchdrop_sftp_sensor

couchdrop_sftp_sensor = build_couchdrop_sftp_sensor(
    code_location=CODE_LOCATION,
    local_timezone=LOCAL_TIMEZONE,
    asset_selection=[view_count_per_view, psat],
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
