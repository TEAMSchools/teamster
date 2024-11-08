from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf._google.sheets.assets import asset_specs
from teamster.libraries.google.sheets.sensors import build_google_sheets_asset_sensor

google_sheets_asset_sensor = build_google_sheets_asset_sensor(
    code_location=CODE_LOCATION,
    minimum_interval_seconds=(60 * 10),
    asset_specs=asset_specs,
)

sensors = [
    google_sheets_asset_sensor,
]
