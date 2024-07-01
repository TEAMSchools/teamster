from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.tableau.assets import external_assets
from teamster.libraries.tableau.sensors import build_tableau_asset_sensor

tableau_asset_sensor = build_tableau_asset_sensor(
    name=f"{CODE_LOCATION}_tableau_asset_sensor",
    asset_selection=external_assets,
    minimum_interval_seconds=(60 * 10),
)

sensors = [
    tableau_asset_sensor,
]
