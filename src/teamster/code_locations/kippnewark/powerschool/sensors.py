from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.powerschool.assets import assets
from teamster.libraries.powerschool.sis.sensors import build_powerschool_asset_sensor

powerschool_asset_sensor = build_powerschool_asset_sensor(
    code_location=CODE_LOCATION,
    asset_selection=assets,
    execution_timezone=LOCAL_TIMEZONE,
    minimum_interval_seconds=(60 * 15),
)

sensors = [
    powerschool_asset_sensor,
]
