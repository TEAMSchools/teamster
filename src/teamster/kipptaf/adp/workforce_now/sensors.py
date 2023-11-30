from teamster.core.adp.workforce_now.sensors import build_adp_wfn_sftp_sensor

from ... import CODE_LOCATION, LOCAL_TIMEZONE
from .assets import adp_wfn_sftp_assets

adp_wfn_sftp_sensor = build_adp_wfn_sftp_sensor(
    code_location=CODE_LOCATION,
    asset_defs=adp_wfn_sftp_assets,
    timezone=LOCAL_TIMEZONE,
    minimum_interval_seconds=(60 * 10),
)
