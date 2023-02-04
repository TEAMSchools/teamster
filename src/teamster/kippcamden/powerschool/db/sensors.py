from dagster import AssetSelection

from teamster.core.powerschool.db.sensors import (
    build_powerschool_incremental_sensor,
    powerschool_ssh_tunnel,
)
from teamster.kippcamden.powerschool.db import assets

# assignments_sensor = build_powerschool_incremental_sensor(
#     name="ps_assignments_sensor",
#     asset_selection=AssetSelection.assets(*assets.assignments_assets),
#     where_column="whenmodified",
#     minimum_interval_seconds=90,
# )

# extensions_sensor = build_powerschool_incremental_sensor(
#     name="ps_extensions_sensor",
#     asset_selection=AssetSelection.assets(*assets.extensions_assets),
#     where_column="whenmodified",
#     minimum_interval_seconds=90,
# )

# contacts_sensor = build_powerschool_incremental_sensor(
#     name="ps_contacts_sensor",
#     asset_selection=AssetSelection.assets(*assets.contacts_assets),
#     where_column="whenmodified",
#     minimum_interval_seconds=90,
# )

# whenmodified_sensor = build_powerschool_incremental_sensor(
#     name="ps_whenmodified_sensor",
#     asset_selection=AssetSelection.assets(*assets.whenmodified_assets),
#     where_column="whenmodified",
#     minimum_interval_seconds=90,
# )

whenmodified_sensor = build_powerschool_incremental_sensor(
    name="ps_whenmodified_sensor",
    asset_selection=AssetSelection.assets(*assets.assets),
    where_column="whenmodified",
    minimum_interval_seconds=90,
)

transactiondate_sensor = build_powerschool_incremental_sensor(
    name="ps_transactiondate_sensor",
    asset_selection=AssetSelection.assets(*assets.transactiondate_assets),
    where_column="transaction_date",
    minimum_interval_seconds=90,
)

__all__ = [
    powerschool_ssh_tunnel,
    # assignments_sensor,
    # contacts_sensor,
    # extensions_sensor,
    whenmodified_sensor,
    transactiondate_sensor,
]
