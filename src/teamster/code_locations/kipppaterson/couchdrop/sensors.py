from teamster.code_locations.kipppaterson import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipppaterson.finalsite.assets import status_report
from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets
from teamster.libraries.couchdrop.sensors import build_couchdrop_sftp_sensor

couchdrop_sftp_sensor = build_couchdrop_sftp_sensor(
    code_location=CODE_LOCATION,
    local_timezone=LOCAL_TIMEZONE,
    asset_selection=[*assets, status_report],
    minimum_interval_seconds=(60 * 10),
    folder_id="1vsh02kpWEGJedLNa0VcbwRSUUOWTtrUd",
)

sensors = [
    couchdrop_sftp_sensor,
]
