from teamster.kipptaf.google.sheets.sensors import build_google_sheets_asset_sensor

from .assets import _all as google_sheets_assets

google_sheets_asset_sensor = build_google_sheets_asset_sensor(google_sheets_assets)

_all = [
    google_sheets_asset_sensor,
]
