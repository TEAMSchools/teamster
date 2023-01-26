from dagster import build_resources, config_from_files, sensor
from dagster._core.definitions.asset_reconciliation_sensor import (
    AssetReconciliationCursor,
    reconcile,
)
from sqlalchemy import text

from teamster.core.resources.sqlalchemy import oracle
from teamster.core.resources.ssh import ssh_resource


def build_powerschool_incremental_sensor(name, asset_selection, where_col):
    @sensor(name=name, asset_selection=asset_selection)
    def _sensor(context):
        cursor = (
            AssetReconciliationCursor.from_serialized(
                context.cursor, context.repository_def.asset_graph
            )
            if context.cursor
            else AssetReconciliationCursor.empty()
        )

        run_requests, updated_cursor = reconcile(
            repository_def=context.repository_def,
            asset_selection=asset_selection,
            instance=context.instance,
            cursor=cursor,
            run_tags=None,
        )
        context.log.info(updated_cursor)
        context.log.debug(
            updated_cursor.materialized_or_requested_root_partitions_by_asset_key
        )

        with build_resources(
            {
                "ps_db": oracle.configured(
                    config_from_files(
                        ["src/teamster/core/resources/config/db_powerschool.yaml"]
                    )
                ),
                "ps_ssh": ssh_resource.configured(
                    config_from_files(
                        ["src/teamster/core/resources/config/ssh_powerschool.yaml"]
                    )
                ),
            }
        ) as resources:
            # ssh_tunnel = resources.ps_ssh.get_tunnel()

            # context.log.debug("Starting SSH tunnel")
            # ssh_tunnel.start()

            # asset_keys = {}
            for (
                asset_key,
                time_window_partitions_subset,
            ) in (
                updated_cursor.materialized_or_requested_root_partitions_by_asset_key.items()
            ):
                context.log.info(asset_key)
                for window in time_window_partitions_subset._included_time_windows:
                    context.log.info(window.start)
                    context.log.info(window.end)
        # for tw in v["time_windows"]:
        #     query = text(
        #         f"SELECT COUNT(*) FROM {k.split('/')[-1]} WHERE {where_col}"
        #     )

        #     [(count,)] = context.resources.ps_db.execute_query(
        #         query=query,
        #         partition_size=1,
        #         output=None,
        #     )

        #     context.log.info(f"Found {count} rows")
        #     if count > 0:
        #         asset_keys[k] = v

        # context.log.debug(asset_keys)

        # context.log.debug("Stopping SSH tunnel")
        # ssh_tunnel.stop()

        # context.update_cursor(updated_cursor.serialize())
        # return run_requests

    return _sensor
