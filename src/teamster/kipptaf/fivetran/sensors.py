from teamster.core.fivetran.sensors import build_fivetran_sync_monitor_sensor

from .. import CODE_LOCATION
from . import assets

fivetran_sync_monitor_sensor = build_fivetran_sync_monitor_sensor(
    code_location=CODE_LOCATION, asset_defs=assets
)

__all__ = [
    fivetran_sync_monitor_sensor,
]
