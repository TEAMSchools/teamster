from teamster.core.couchdrop.sensors import build_couchdrop_sftp_sensor
from teamster.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.kipptaf.performance_management.assets import observation_details

couchdrop_sftp_sensor = build_couchdrop_sftp_sensor(
    code_location=CODE_LOCATION,
    local_timezone=LOCAL_TIMEZONE,
    assets=[observation_details],
)

sensors = [
    couchdrop_sftp_sensor,
]
