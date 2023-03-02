from dagster import AssetSelection, SensorEvaluationContext, sensor
from dagster._core.definitions.asset_reconciliation_sensor import (
    AssetReconciliationCursor,
    find_never_materialized_or_requested_root_asset_partitions,
)
from dagster._utils.caching_instance_queryer import CachingInstanceQueryer

from teamster.core.powerschool.db.sensors import (
    build_powerschool_incremental_sensor,
    powerschool_ssh_tunnel,
)
from teamster.test.powerschool.db import assets

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


@sensor(
    # name=name,
    asset_selection=AssetSelection.assets(*assets.whenmodified_assets),
    # minimum_interval_seconds=minimum_interval_seconds,
    # description=description,
    # default_status=default_status,
)
def test_dynamic_partition_sensor(context: SensorEvaluationContext):
    cursor = (
        AssetReconciliationCursor.from_serialized(
            context.cursor, context.repository_def.asset_graph
        )
        if context.cursor
        else AssetReconciliationCursor.empty()
    )

    (
        never_materialized_or_requested_roots,
        newly_materialized_root_asset_keys,
        newly_materialized_root_partitions_by_asset_key,
    ) = find_never_materialized_or_requested_root_asset_partitions(
        instance_queryer=CachingInstanceQueryer(instance=context.instance),
        cursor=cursor,
        target_asset_selection=AssetSelection.assets(*assets.whenmodified_assets),
        asset_graph=context.repository_def.asset_graph,
    )

    context.log.info(never_materialized_or_requested_roots)
    context.log.info(newly_materialized_root_asset_keys)
    context.log.info(newly_materialized_root_partitions_by_asset_key)


__all__ = [
    powerschool_ssh_tunnel,
    whenmodified_sensor,
    transactiondate_sensor,
    test_dynamic_partition_sensor,
]
