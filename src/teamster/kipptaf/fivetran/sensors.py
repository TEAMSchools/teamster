from teamster.core.fivetran.sensors import build_fivetran_sync_monitor_sensor
from teamster.kipptaf.fivetran import assets

from .. import CODE_LOCATION

fivetran_sync_monitor_sensor = build_fivetran_sync_monitor_sensor(
    code_location=CODE_LOCATION, asset_defs=assets
)

__all__ = [
    fivetran_sync_monitor_sensor,
]
