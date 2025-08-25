from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.powerschool.assets import (
    powerschool_table_assets_full,
    powerschool_table_assets_no_partition,
    powerschool_table_assets_transaction_date,
)
from teamster.libraries.powerschool.sis.odbc.sensors import (
    build_powerschool_asset_sensor,
)

powerschool_asset_sensor = build_powerschool_asset_sensor(
    code_location=CODE_LOCATION,
    asset_selection=[
        *powerschool_table_assets_full,
        *powerschool_table_assets_no_partition,
        *powerschool_table_assets_transaction_date,
    ],
    execution_timezone=LOCAL_TIMEZONE,
    minimum_interval_seconds=(60 * 15),
    max_runtime_seconds=(60 * 10),
)

sensors = [
    powerschool_asset_sensor,
]
