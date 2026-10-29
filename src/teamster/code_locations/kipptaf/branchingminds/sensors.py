from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.branchingminds.assets import assets
from teamster.libraries.branchingminds.sensors import build_branchingminds_sftp_sensor

sftp_sensor = build_branchingminds_sftp_sensor(
    code_location=CODE_LOCATION,
    timezone=LOCAL_TIMEZONE,
    asset_selection=assets,
    remote_dir="/exports",
    minimum_interval_seconds=(60 * 10),
)

sensors = [
    sftp_sensor,
]
