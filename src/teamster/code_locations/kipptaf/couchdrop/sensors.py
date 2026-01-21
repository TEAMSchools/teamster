from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.collegeboard.assets import (
    assets as collegeboard_assets,
)
from teamster.code_locations.kipptaf.nsc.assets import assets as nsc_assets
from teamster.code_locations.kipptaf.tableau.assets import view_count_per_view
from teamster.libraries.couchdrop.sensors import build_couchdrop_sftp_sensor

couchdrop_sftp_sensor = build_couchdrop_sftp_sensor(
    code_location=CODE_LOCATION,
    local_timezone=LOCAL_TIMEZONE,
    asset_selection=[view_count_per_view, *collegeboard_assets, *nsc_assets],
    minimum_interval_seconds=(60 * 10),
    folder_id="1B40ZL6jjXPMP3FDaHduqwbYmiEbfByNR",
    exclude_dirs=[
        f"/data-team/{CODE_LOCATION}/dayforce",
        f"/data-team/{CODE_LOCATION}/njdoe",
        f"/data-team/{CODE_LOCATION}/performance-management",
        f"/data-team/{CODE_LOCATION}/surveys",
    ],
)

sensors = [
    couchdrop_sftp_sensor,
]
