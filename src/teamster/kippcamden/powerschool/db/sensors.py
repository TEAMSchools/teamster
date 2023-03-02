# import os

from dagster import (  # build_resources,; config_from_files,
    AssetSelection,
    SensorEvaluationContext,
    sensor,
)
from dagster._core.definitions.asset_reconciliation_sensor import (
    AssetReconciliationCursor,
)

from teamster.core.powerschool.db.sensors import (
    build_powerschool_incremental_sensor,
    powerschool_ssh_tunnel,
)
from teamster.kippcamden.powerschool.db import assets

# from dagster_ssh import ssh_resource


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


# def filter_asset_partitions(
#     context: SensorEvaluationContext, resources, asset_partitions, sql_string: str
# ):
#     asset_partitions_sorted = sorted(
#         asset_partitions, key=lambda x: x.partition_key, reverse=True
#     )

#     asset_keys_filtered = set()
#     for akpk in asset_partitions_sorted:
#         context.log.debug(akpk)

#         window_start = pendulum.parse(text=akpk.partition_key, tz=LOCAL_TIME_ZONE.name)
#         window_end = window_start.add(days=1)
#         query = text(
#             sql_string.format(
#                 table_name=akpk.asset_key.path[-1],
#                 window_start=window_start.format("YYYY-MM-DDTHH:mm:ss.SSSSSS"),
#                 window_end=window_end.format("YYYY-MM-DDTHH:mm:ss.SSSSSS"),
#             )
#         )

#         try:
#             [(count,)] = resources.ps_db.execute_query(
#                 query=query,
#                 partition_size=1,
#                 output=None,
#             )
#         except (exc.OperationalError, exc.DatabaseError, exc.ResourceClosedError) as e:
#             context.log.error(e)

#             # wait 1 sec and try again once
#             time.sleep(1)
#             try:
#                 context.log.debug("Retrying")
#                 [(count,)] = resources.ps_db.execute_query(
#                     query=query,
#                     partition_size=1,
#                     output=None,
#                 )
#             except Exception as e:
#                 context.log.error(e)
#                 continue

#         context.log.debug(f"count: {count}")
#         if count > 0:
#             asset_keys_filtered.add(akpk)

#     return asset_keys_filtered


@sensor(asset_selection=AssetSelection.assets(*assets.whenmodified_assets))
def test_dynamic_partition_sensor(context: SensorEvaluationContext):
    target_asset_selection = AssetSelection.assets(*assets.whenmodified_assets)

    asset_graph = context.repository_def.asset_graph

    cursor = (
        AssetReconciliationCursor.from_serialized(context.cursor, asset_graph)
        if context.cursor
        else AssetReconciliationCursor.empty()
    )

    # check if asset has ever been materialized or requested
    never_materialized_or_requested = set(
        asset_key
        for asset_key in target_asset_selection.resolve(asset_graph.assets)
        if not cursor.was_previously_materialized_or_requested(asset_key)
    )
    context.log.info(never_materialized_or_requested)

    # # init powerschool tunnel
    # with build_resources(
    #     resources={"ps_ssh": ssh_resource},
    #     resource_config={
    #         "ps_ssh": {
    #             "config": config_from_files(
    #                 ["src/teamster/core/resources/config/ssh_powerschool.yaml"]
    #             )
    #         }
    #     },
    # ) as resources:
    #     ssh_port = 1521
    #     ssh_tunnel = resources.ps_ssh.get_tunnel(
    #         remote_port=ssh_port,
    #         remote_host=os.getenv("PS_SSH_REMOTE_BIND_HOST"),
    #         local_port=ssh_port,
    #     )
    #     ssh_tunnel.check_tunnels()
    #     context.log.debug(f"tunnel_is_up: {ssh_tunnel.tunnel_is_up}")

    #     if ssh_tunnel.tunnel_is_up.get(("127.0.0.1", ssh_port)):
    #         context.log.info("Tunnel is up")
    #         ssh_tunnel.restart()
    #     else:
    #         context.log.info("Starting SSH tunnel")
    #         ssh_tunnel.start()

    #     try:
    #         ...
    #     finally:
    #         context.log.info("Stopping SSH tunnel")
    #         ssh_tunnel.stop()


__all__ = [
    powerschool_ssh_tunnel,
    whenmodified_sensor,
    transactiondate_sensor,
    test_dynamic_partition_sensor,
]
