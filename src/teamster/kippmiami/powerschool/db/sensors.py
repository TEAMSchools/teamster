from dagster import AssetSelection

from teamster.core.powerschool.db.sensors import (
    build_powerschool_incremental_sensor,
    powerschool_ssh_tunnel,
)
from teamster.kippmiami.powerschool.db import assets

whenmodified_sensor = build_powerschool_incremental_sensor(
    name="ps_whenmodified_sensor",
    asset_selection=AssetSelection.assets(*assets.whenmodified_assets),
    where_column="whenmodified",
    minimum_interval_seconds=3600,
)

transactiondate_sensor = build_powerschool_incremental_sensor(
    name="ps_transactiondate_sensor",
    asset_selection=AssetSelection.assets(*assets.transactiondate_assets),
    where_column="transaction_date",
    minimum_interval_seconds=3600,
)

__all__ = [powerschool_ssh_tunnel, whenmodified_sensor, transactiondate_sensor]
