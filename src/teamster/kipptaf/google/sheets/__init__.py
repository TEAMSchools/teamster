from .assets import _all as assets
from .sensors import build_google_sheets_asset_sensor

sensors = build_google_sheets_asset_sensor(assets)

_all = [
    assets,
    sensors,
]
