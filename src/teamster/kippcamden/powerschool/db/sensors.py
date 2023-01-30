from dagster import AssetSelection

from teamster.core.powerschool.db.sensors import (
    build_powerschool_incremental_sensor,
    powerschool_ssh_tunnel,
)
from teamster.kippcamden.powerschool.db import assets

whenmodified_sensors = [
    build_powerschool_incremental_sensor(
        name="ps_whenmodified_sensor",
        asset_selection=AssetSelection.assets(*assets.whenmodified_assets),
        where_column="whenmodified",
        minimum_interval_seconds=60,
    )
]

transactiondate_sensor = build_powerschool_incremental_sensor(
    name="ps_transactiondate_sensor",
    asset_selection=AssetSelection.assets(*assets.transactiondate_assets),
    where_column="transaction_date",
    minimum_interval_seconds=60,
)

__all__ = whenmodified_sensors + [transactiondate_sensor, powerschool_ssh_tunnel]
