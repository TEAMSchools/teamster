from teamster.code_locations.kippnewark import (
    CODE_LOCATION,
    CURRENT_FISCAL_YEAR,
    LOCAL_TIMEZONE,
)
from teamster.code_locations.kippnewark.renlearn import assets
from teamster.libraries.renlearn.sensors import build_renlearn_sftp_sensor

sftp_sensor = build_renlearn_sftp_sensor(
    code_location=CODE_LOCATION,
    asset_defs=assets,
    fiscal_year=CURRENT_FISCAL_YEAR,
    timezone=LOCAL_TIMEZONE,
    minimum_interval_seconds=(60 * 10),
)

sensors = [
    sftp_sensor,
]
