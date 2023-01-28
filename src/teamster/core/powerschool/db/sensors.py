# import pendulum
from dagster import (  # build_resources,; config_from_files,
    MultiAssetSensorEvaluationContext,
    multi_asset_sensor,
)

# from teamster.core.resources.sqlalchemy import oracle
# from teamster.core.resources.ssh import ssh_resource

# from teamster.core.utils.variables import LOCAL_TIME_ZONE

# from dagster._core.definitions.asset_reconciliation_sensor import (
#     AssetReconciliationCursor,
#     build_run_requests,
# )
# from dagster._core.definitions.events import AssetKeyPartitionKey
# from sqlalchemy import text


def build_powerschool_incremental_sensor(
    name, asset_selection, where_column, run_tags=None
):
    @multi_asset_sensor(name=name, asset_selection=asset_selection)
    def _sensor(context: MultiAssetSensorEvaluationContext):
        materialization_records = (
            context.latest_materialization_records_by_partition_and_asset()
        )
        context.log.info(materialization_records)

        run_requests = []
        for partition, materializations_by_asset in materialization_records.items():
            context.log.info(partition)
            context.log.info(materializations_by_asset)

            foo = []
            for asset_key in context.asset_keys:
                context.log.info(asset_key)
                bar = context.all_partitions_materialized(asset_key, [partition])
                context.log.info(bar)
                foo.append(bar)

            if all(bar):
                # run_requests.append(
                #     downstream_daily_job.run_request_for_partition(partition)
                # )
                for asset_key, materialization in materializations_by_asset.items():
                    context.log.info(asset_key)
                    context.log.info(materialization)
                    if asset_key in context.asset_keys:
                        context.advance_cursor({asset_key: materialization})

        return run_requests

        # materialization_records = {
        #     ak: context.materialization_records_for_key(asset_key=ak, limit=25)
        #     for ak in context.asset_keys
        # }
        # context.log.info(materialization_records)

        for (
            asset_key,
            event_log_record,
        ) in materialization_records.items():
            context.log.info(asset_key)
            context.log.info(event_log_record)

        trailing_unconsumed_events = {
            ak: context.get_trailing_unconsumed_events(asset_key=ak)
            for ak in context.asset_keys
        }
        context.log.info(trailing_unconsumed_events)

        # with build_resources(
        #     resources={
        #         "ps_db": oracle,
        #         "ps_ssh": ssh_resource,
        #     },
        #     resource_config={
        #         "ps_db": {
        #             "config": config_from_files(
        #                 ["src/teamster/core/resources/config/db_powerschool.yaml"]
        #             )
        #         },
        #         "ps_ssh": {
        #             "config": config_from_files(
        #                 ["src/teamster/core/resources/config/ssh_powerschool.yaml"]
        #             )
        #         },
        #     },
        # ) as resources:
        #     ssh_tunnel = resources.ps_ssh.get_tunnel()
        #     ssh_tunnel.start()

        # ssh_tunnel.stop()

    return _sensor


# def build_powerschool_incremental_sensor(
#     name, asset_selection, where_column, run_tags=None
# ):
#     @sensor(name=name, asset_selection=asset_selection, minimum_interval_seconds=60)
#     def _sensor(context):
#         cursor = (
#             AssetReconciliationCursor.from_serialized(
#                 context.cursor, context.repository_def.asset_graph
#             )
#             if context.cursor
#             else AssetReconciliationCursor.empty()
#         )

#         run_requests, updated_cursor = reconcile(
#             repository_def=context.repository_def,
#             asset_selection=asset_selection,
#             instance=context.instance,
#             cursor=cursor,
#             run_tags=run_tags,
#         )

#         with build_resources(
#             resources={
#                 "ps_db": oracle,
#                 "ps_ssh": ssh_resource,
#             },
#             resource_config={
#                 "ps_db": {
#                     "config": config_from_files(
#                         ["src/teamster/core/resources/config/db_powerschool.yaml"]
#                     )
#                 },
#                 "ps_ssh": {
#                     "config": config_from_files(
#                         ["src/teamster/core/resources/config/ssh_powerschool.yaml"]
#                     )
#                 },
#             },
#         ) as resources:
#             ssh_tunnel = resources.ps_ssh.get_tunnel()
#             ssh_tunnel.start()

#             asset_partitions = []
#             asset_keys_filtered = {}
#             for (
#                 asset_key,
#                 time_window_partitions_subset,
#             ) in (
#                 updated_cursor.materialized_or_requested_root_partitions_by_asset_key.items()
#             ):
#                 for pk in time_window_partitions_subset.get_partition_keys():
#                     window_start = pendulum.parse(text=pk, tz=LOCAL_TIME_ZONE.name)
#                     window_end = window_start.add(hours=1)

#                     query = text(
#                         (
#                             f"SELECT COUNT(*) "
#                             f"FROM {asset_key.path[-1]} "
#                             f"WHERE {where_column} >= TO_TIMESTAMP("
#                             f"'{window_start.format('YYYY-MM-DDTHH:mm:ss.SSSSSS')}', "
#                             "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6') "
#                             f"AND {where_column} < TO_TIMESTAMP("
#                             f"'{window_end.format('YYYY-MM-DDTHH:mm:ss.SSSSSS')}', "
#                             "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
#                         )
#                     )
#                     context.log.debug(query)

#                     [(count,)] = resources.ps_db.execute_query(
#                         query=query,
#                         partition_size=1,
#                         output=None,
#                     )
#                     context.log.debug(f"count: {count}")

#                     if count > 0:
#                         asset_partitions.append(
#                             AssetKeyPartitionKey(asset_key=asset_key, partition_key=pk)
#                         )
#                         asset_keys_filtered[asset_key] = time_window_partitions_subset

#         ssh_tunnel.stop()

#         cursor_filtered = AssetReconciliationCursor(
#             latest_storage_id=updated_cursor.latest_storage_id,
#             materialized_or_requested_root_asset_keys=set(),
#             materialized_or_requested_root_partitions_by_asset_key=asset_keys_filtered,
#         )

#         run_requests = build_run_requests(
#             asset_partitions=asset_partitions,
#             asset_graph=context.repository_def.asset_graph,
#             run_tags=run_tags,
#         )

#         # run_requests, updated_cursor = reconcile(
#         #     repository_def=context.repository_def,
#         #     asset_selection=AssetSelection.keys(*asset_keys_filtered),
#         #     instance=context.instance,
#         #     cursor=cursor,
#         #     run_tags=run_tags,
#         # )

#         context.update_cursor(cursor_filtered.serialize())
#         return run_requests

#     return _sensor
