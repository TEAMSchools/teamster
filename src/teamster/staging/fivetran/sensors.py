from teamster.core.fivetran.sensors import build_fivetran_sync_status_sensor
from teamster.staging.fivetran import assets

from .. import CODE_LOCATION

fivetran_sync_status_sensor = build_fivetran_sync_status_sensor(
    code_location=CODE_LOCATION, asset_defs=assets
)

__all__ = [
    fivetran_sync_status_sensor,
]
