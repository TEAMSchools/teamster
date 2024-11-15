from teamster.code_locations.kippmiami import (
    CODE_LOCATION,
    CURRENT_FISCAL_YEAR,
    LOCAL_TIMEZONE,
)
from teamster.code_locations.kippmiami.renlearn import assets
from teamster.libraries.renlearn.sensors import build_renlearn_sftp_sensor

sftp_sensor = build_renlearn_sftp_sensor(
    code_location=CODE_LOCATION,
    asset_selection=assets,
    partition_key_start_date=CURRENT_FISCAL_YEAR.start.isoformat(),
    timezone=LOCAL_TIMEZONE,
    minimum_interval_seconds=(60 * 10),
)

sensors = [
    sftp_sensor,
]
