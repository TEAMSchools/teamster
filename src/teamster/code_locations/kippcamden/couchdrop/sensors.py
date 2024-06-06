from teamster.code_locations.kippcamden import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippcamden.pearson.assets import assets
from teamster.libraries.couchdrop.sensors import build_couchdrop_sftp_sensor

couchdrop_sftp_sensor = build_couchdrop_sftp_sensor(
    code_location=CODE_LOCATION, local_timezone=LOCAL_TIMEZONE, assets=assets
)

sensors = [
    couchdrop_sftp_sensor,
]
