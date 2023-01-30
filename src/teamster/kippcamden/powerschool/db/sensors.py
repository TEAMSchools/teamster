from dagster import AssetSelection

from teamster.core.powerschool.db.sensors import (
    build_powerschool_incremental_sensor,
    powerschool_ssh_tunnel,
)
from teamster.kippcamden.powerschool.db import assets

whenmodified_incremental_sensors = [
    build_powerschool_incremental_sensor(
        name=a.key.to_python_identifier(),
        asset_selection=AssetSelection.assets(a),
        where_column="whenmodified",
        minimum_interval_seconds=60,
    )
    for a in assets.whenmodified_assets
]

transactiondate_incremental_sensors = [
    build_powerschool_incremental_sensor(
        name=a.key.to_python_identifier(),
        asset_selection=AssetSelection.assets(a),
        where_column="transaction_date",
    )
    for a in assets.transactiondate_assets
]

__all__ = (
    whenmodified_incremental_sensors
    + transactiondate_incremental_sensors
    + [powerschool_ssh_tunnel]
)
