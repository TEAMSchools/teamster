from teamster.core.renlearn.sensors import build_sftp_sensor

from .. import CODE_LOCATION
from . import assets

sftp_sensor = build_sftp_sensor(code_location=CODE_LOCATION, asset_selection=assets)

__all__ = [
    sftp_sensor,
]
