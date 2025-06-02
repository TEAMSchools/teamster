from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.fldoe.assets import assets
from teamster.libraries.couchdrop.sensors import build_couchdrop_sftp_sensor

couchdrop_sftp_sensor = build_couchdrop_sftp_sensor(
    code_location=CODE_LOCATION,
    local_timezone=LOCAL_TIMEZONE,
    asset_selection=assets,
    minimum_interval_seconds=(60 * 10),
    folder_id="1BLu_qlbcw_jcRZ8m9KIib0UbkPgK4uiM",
    exclude_dirs=[f"/data-team/{CODE_LOCATION}/fldoe/fsa"],
)

sensors = [
    couchdrop_sftp_sensor,
]
