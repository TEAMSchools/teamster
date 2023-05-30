from teamster.core.google.sensors import build_gsheet_sensor

from .. import CODE_LOCATION
from .assets import gsheet_assets

gsheets_sensor = build_gsheet_sensor(
    code_location=CODE_LOCATION, asset_defs=gsheet_assets, minimum_interval_seconds=600
)

__all__ = [
    gsheets_sensor,
]
