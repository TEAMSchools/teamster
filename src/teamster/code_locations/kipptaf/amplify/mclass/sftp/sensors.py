from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.amplify.mclass.sftp.assets import assets
from teamster.libraries.amplify.mclass.sftp.sensors import (
    build_amplify_mclass_sftp_sensor,
)

amplify_mclass_sftp_sensor = build_amplify_mclass_sftp_sensor(
    code_location=CODE_LOCATION,
    timezone=LOCAL_TIMEZONE,
    asset_selection=assets,
    remote_dir_regex=r"/",
    minimum_interval_seconds=(60 * 5),
)

sensors = [
    amplify_mclass_sftp_sensor,
]
