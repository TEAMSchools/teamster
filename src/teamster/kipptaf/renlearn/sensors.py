from teamster.core.renlearn.sensors import build_sftp_sensor

from .. import CODE_LOCATION
from . import assets

sftp_sensor = build_sftp_sensor(
    code_location=CODE_LOCATION,
    source_system="renlearn",
    asset_defs=assets,
    minimum_interval_seconds=600,
)

__all__ = [
    sftp_sensor,
]
