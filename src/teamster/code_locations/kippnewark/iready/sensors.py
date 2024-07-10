from teamster.code_locations.kippnewark import (
    CODE_LOCATION,
    CURRENT_FISCAL_YEAR,
    LOCAL_TIMEZONE,
)
from teamster.code_locations.kippnewark.iready import assets
from teamster.libraries.iready.sensors import build_iready_sftp_sensor

sftp_sensor = build_iready_sftp_sensor(
    code_location=CODE_LOCATION,
    asset_defs=assets,
    timezone=LOCAL_TIMEZONE,
    remote_dir_regex=r"/exports/nj-kipp_nj",
    current_fiscal_year=CURRENT_FISCAL_YEAR.fiscal_year,
    minimum_interval_seconds=(60 * 10),
)

sensors = [
    sftp_sensor,
]
