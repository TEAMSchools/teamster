from dagster import build_resources, sensor
from dagster._core.definitions.asset_reconciliation_sensor import (
    AssetReconciliationCursor,
    reconcile,
)
from sqlalchemy import text


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

        with build_resources({"ps_db", "ps_ssh"}) as resources:
            ssh_tunnel = resources.ps_ssh.get_tunnel()

            context.log.debug("Starting SSH tunnel")
            ssh_tunnel.start()

            asset_keys = {}
            for (
                k,
                v,
            ) in (
                updated_cursor.materialized_or_requested_root_partitions_by_asset_key.items()
            ):
                context.log.debug(k, v)
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

            context.log.debug("Stopping SSH tunnel")
            ssh_tunnel.stop()

        # context.update_cursor(updated_cursor.serialize())
        # return run_requests

    return _sensor
