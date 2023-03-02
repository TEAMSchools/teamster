from dagster import AssetSelection, SensorEvaluationContext, sensor
from dagster._core.definitions.asset_reconciliation_sensor import (
    AssetReconciliationCursor,
)
from dagster._core.definitions.events import AssetKeyPartitionKey
from dagster._utils.caching_instance_queryer import CachingInstanceQueryer

from teamster.core.powerschool.db.sensors import (
    build_powerschool_incremental_sensor,
    powerschool_ssh_tunnel,
)
from teamster.kippcamden.powerschool.db import assets

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


@sensor(asset_selection=AssetSelection.assets(*assets.whenmodified_assets))
def test_dynamic_partition_sensor(context: SensorEvaluationContext):
    target_asset_selection = AssetSelection.assets(*assets.whenmodified_assets)

    instance_queryer = CachingInstanceQueryer(instance=context.instance)
    asset_graph = context.repository_def.asset_graph

    cursor = (
        AssetReconciliationCursor.from_serialized(context.cursor, asset_graph)
        if context.cursor
        else AssetReconciliationCursor.empty()
    )

    never_materialized_or_requested = set()
    for asset_key in target_asset_selection.resolve(asset_graph):
        if not cursor.was_previously_materialized_or_requested(asset_key):
            asset = AssetKeyPartitionKey(asset_key)
            if not instance_queryer.get_latest_materialization_record(asset, None):
                never_materialized_or_requested.add(asset)

    context.log.info(never_materialized_or_requested)


__all__ = [
    powerschool_ssh_tunnel,
    whenmodified_sensor,
    transactiondate_sensor,
    test_dynamic_partition_sensor,
]
