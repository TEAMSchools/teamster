from teamster.code_locations.kippcamden import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippcamden.cambium.assets import eoc as cambium_eoc
from teamster.code_locations.kippcamden.cambium.assets import njgpa as cambium_njgpa
from teamster.code_locations.kippcamden.cambium.assets import njsla as cambium_njsla
from teamster.code_locations.kippcamden.finalsite.assets import status_report
from teamster.libraries.couchdrop.sensors import build_couchdrop_sftp_sensor

couchdrop_sftp_sensor = build_couchdrop_sftp_sensor(
    code_location=CODE_LOCATION,
    local_timezone=LOCAL_TIMEZONE,
    asset_selection=[cambium_eoc, cambium_njgpa, cambium_njsla, status_report],
    minimum_interval_seconds=(60 * 10),
    folder_id="1BKZgGl_LcHIOVLrDo8eMMZLGFsc2Nk1o",
    exclude_dirs=[
        f"/data-team/{CODE_LOCATION}/edplan",
        f"/data-team/{CODE_LOCATION}/pearson",
    ],
)

sensors = [
    couchdrop_sftp_sensor,
]
