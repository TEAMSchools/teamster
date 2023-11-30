from teamster.core.google.sheets.sensors import build_gsheet_sensor

from ... import CODE_LOCATION
from .assets import google_sheets_assets

google_sheets_sensor = build_gsheet_sensor(
    code_location=CODE_LOCATION,
    asset_defs=google_sheets_assets,
    minimum_interval_seconds=(60 * 10),
)
