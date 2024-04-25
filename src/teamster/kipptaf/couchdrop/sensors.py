from teamster.core.couchdrop.sensors import build_couchdrop_sftp_sensor
from teamster.kipptaf.adp.payroll.assets import general_ledger_file
from teamster.kipptaf.performance_management.assets import observation_details

from .. import CODE_LOCATION, LOCAL_TIMEZONE

couchdrop_sftp_sensor = build_couchdrop_sftp_sensor(
    code_location=CODE_LOCATION,
    local_timezone=LOCAL_TIMEZONE,
    assets=[general_ledger_file, observation_details],
)

__all__ = [
    couchdrop_sftp_sensor,
]
