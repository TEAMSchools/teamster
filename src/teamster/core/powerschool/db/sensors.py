# import gc
import os
from typing import AbstractSet, Generator, Mapping, Optional

import dagster._check as check
import pendulum
from dagster import (
    AssetSelection,
    DagsterInstance,
    DefaultSensorStatus,
    RepositoryDefinition,
    SensorDefinition,
    SensorEvaluationContext,
    build_resources,
    config_from_files,
    sensor,
)
from dagster._core.definitions.asset_reconciliation_sensor import (
    AssetReconciliationCursor,
    build_run_requests,
    determine_asset_partitions_to_reconcile,
    determine_asset_partitions_to_reconcile_for_freshness,
)
from dagster._core.definitions.events import AssetKeyPartitionKey
from dagster._core.definitions.scoped_resources_builder import Resources
from dagster._core.definitions.utils import check_valid_name
from dagster._utils.caching_instance_queryer import CachingInstanceQueryer
from dagster_ssh import ssh_resource
from sqlalchemy import text

from teamster.core.resources.sqlalchemy import oracle
from teamster.core.utils.variables import LOCAL_TIME_ZONE


def filter_asset_partitions(
    context: SensorEvaluationContext,
    resources: Generator[Resources, None, None],
    asset_partitions: AbstractSet[AssetKeyPartitionKey],
    sql_string: str,
) -> AbstractSet[AssetKeyPartitionKey]:
    asset_keys_filtered = set()

    for akpk in asset_partitions:
        context.log.debug(akpk)

        window_start = pendulum.parse(text=akpk.partition_key, tz=LOCAL_TIME_ZONE.name)
        window_end = window_start.add(hours=1)
        query = text(
            sql_string.format(
                table_name=akpk.asset_key.path[-1],
                window_start=window_start.format("YYYY-MM-DDTHH:mm:ss.SSSSSS"),
                window_end=window_end.format("YYYY-MM-DDTHH:mm:ss.SSSSSS"),
            )
        )

        [(count,)] = resources.ps_db.execute_query(
            query=query,
            partition_size=1,
            output=None,
        )

        context.log.debug(f"count: {count}")
        if count > 0:
            asset_keys_filtered.add(akpk)

    return asset_keys_filtered


# based on dagster._core.definitions.asset_reconciliation_sensor.reconcile
def reconcile(
    context: SensorEvaluationContext,
    repository_def: RepositoryDefinition,
    asset_selection: AssetSelection,
    instance: "DagsterInstance",
    cursor: AssetReconciliationCursor,
    run_tags: Optional[Mapping[str, str]],
    sql_string: str,
):
    instance_queryer = CachingInstanceQueryer(instance=instance)
    asset_graph = repository_def.asset_graph

    (
        asset_partitions_to_reconcile_for_freshness,
        eventual_asset_partitions_to_reconcile_for_freshness,
    ) = determine_asset_partitions_to_reconcile_for_freshness(
        instance_queryer=instance_queryer,
        asset_graph=asset_graph,
        target_asset_selection=asset_selection,
    )

    (
        asset_partitions_to_reconcile,
        newly_materialized_root_asset_keys,
        newly_materialized_root_partitions_by_asset_key,
        latest_storage_id,
    ) = determine_asset_partitions_to_reconcile(
        instance_queryer=instance_queryer,
        asset_graph=asset_graph,
        cursor=cursor,
        target_asset_selection=asset_selection,
        eventual_asset_partitions_to_reconcile_for_freshness=eventual_asset_partitions_to_reconcile_for_freshness,
    )

    with build_resources(
        resources={
            "ps_db": oracle,
            "ps_ssh": ssh_resource,
        },
        resource_config={
            "ps_db": {
                "config": config_from_files(
                    ["src/teamster/core/resources/config/db_powerschool.yaml"]
                )
            },
            "ps_ssh": {
                "config": config_from_files(
                    ["src/teamster/core/resources/config/ssh_powerschool.yaml"]
                )
            },
        },
    ) as resources:
        ssh_tunnel = resources.ps_ssh.get_tunnel(
            remote_port=1521,
            remote_host=os.getenv("PS_SSH_REMOTE_BIND_HOST"),
            local_port=1521,
        )

        try:
            ssh_tunnel.start()

            reconcile_filtered = filter_asset_partitions(
                context=context,
                resources=resources,
                asset_partitions=asset_partitions_to_reconcile,
                sql_string=sql_string,
            )
            reconcile_for_freshness_filtered = filter_asset_partitions(
                context=context,
                resources=resources,
                asset_partitions=asset_partitions_to_reconcile_for_freshness,
                sql_string=sql_string,
            )
        finally:
            ssh_tunnel.stop()

    run_requests = build_run_requests(
        asset_partitions=reconcile_filtered | reconcile_for_freshness_filtered,
        asset_graph=asset_graph,
        run_tags=run_tags,
    )

    return run_requests, cursor.with_updates(
        latest_storage_id=latest_storage_id,
        run_requests=run_requests,
        asset_graph=repository_def.asset_graph,
        newly_materialized_root_asset_keys=newly_materialized_root_asset_keys,
        newly_materialized_root_partitions_by_asset_key=newly_materialized_root_partitions_by_asset_key,
    )


# based on dagster.build_asset_reconciliation_sensor
def build_powerschool_incremental_sensor(
    name: str,
    asset_selection: AssetSelection,
    where_column: str,
    minimum_interval_seconds: Optional[int] = None,
    description: Optional[str] = None,
    default_status: DefaultSensorStatus = DefaultSensorStatus.STOPPED,
    run_tags: Optional[Mapping[str, str]] = None,
) -> SensorDefinition:
    check_valid_name(name)
    check.opt_mapping_param(run_tags, "run_tags", key_type=str, value_type=str)

    sql_string = (
        "SELECT COUNT(*) "
        "FROM {table_name} "
        f"WHERE {where_column} >= "
        "TO_TIMESTAMP('{window_start}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6') "
        f"AND {where_column} < "
        "TO_TIMESTAMP('{window_end}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
    )

    @sensor(
        name=name,
        asset_selection=asset_selection,
        minimum_interval_seconds=minimum_interval_seconds,
        description=description,
        default_status=default_status,
    )
    def _sensor(context: SensorEvaluationContext):
        cursor = (
            AssetReconciliationCursor.from_serialized(
                context.cursor, context.repository_def.asset_graph
            )
            if context.cursor
            else AssetReconciliationCursor.empty()
        )

        run_requests, updated_cursor = reconcile(
            context=context,
            repository_def=context.repository_def,
            asset_selection=asset_selection,
            instance=context.instance,
            cursor=cursor,
            run_tags=run_tags,
            sql_string=sql_string,
        )

        context.update_cursor(updated_cursor.serialize())
        # gc.collect()

        return run_requests

    return _sensor
