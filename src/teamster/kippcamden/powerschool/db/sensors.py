import os

import pendulum
from dagster import (
    AssetSelection,
    SensorEvaluationContext,
    build_resources,
    config_from_files,
    sensor,
)
from dagster_ssh import ssh_resource
from sqlalchemy import text

from teamster.core.resources.sqlalchemy import oracle
from teamster.core.utils.variables import LOCAL_TIME_ZONE
from teamster.kippcamden.powerschool.db import assets


def get_asset_count(asset, db):
    partition_column = asset.metadata_by_key[asset.key]["partition_column"]

    window_end = pendulum.now(tz=LOCAL_TIME_ZONE.name).start_of("hour")
    window_start = window_end.subtract(hours=24)

    window_end_fmt = window_end.format("YYYY-MM-DDTHH:mm:ss.SSSSSS")
    window_start_fmt = window_start.format("YYYY-MM-DDTHH:mm:ss.SSSSSS")

    query = text(
        text=" ".join(
            "SELECT COUNT(*)"
            f"FROM {asset.asset_key.path[-1]}"
            f"WHERE {partition_column} >="
            f"TO_TIMESTAMP('{window_start_fmt}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
            f"AND {partition_column} <"
            f"TO_TIMESTAMP('{window_end_fmt}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
        )
    )

    [(count,)] = db.execute_query(
        query=query,
        partition_size=1,
        output=None,
    )

    return count


@sensor(asset_selection=AssetSelection.assets(*assets.partition_assets))
def test_dynamic_partition_sensor(context: SensorEvaluationContext):
    asset_selection = AssetSelection.assets(*assets.partition_assets)

    asset_graph = context.repository_def.asset_graph

    target_assets = [a for a in asset_graph.assets if a.key in asset_selection._keys]

    # check if asset has ever been materialized or requested
    never_materialized_or_requested = set(
        asset_key
        for asset_key in asset_selection.resolve(asset_graph.assets)
        if not context.instance.get_latest_materialization_event(asset_key)
    )
    context.log.info(never_materialized_or_requested)

    # check if asset has any modified records from past X hours
    with build_resources(
        resources={"ssh": ssh_resource, "db": oracle},
        resource_config={
            "ssh": {
                "config": config_from_files(
                    ["src/teamster/core/resources/config/ssh_powerschool.yaml"]
                )
            },
            "db": {
                "config": config_from_files(
                    ["src/teamster/core/resources/config/db_powerschool.yaml"]
                )
            },
        },
    ) as resources:
        ssh_port = 1521
        ssh_tunnel = resources.ssh.get_tunnel(
            remote_port=ssh_port,
            remote_host=os.getenv("PS_SSH_REMOTE_BIND_HOST"),
            local_port=ssh_port,
        )

        ssh_tunnel.check_tunnels()
        if ssh_tunnel.tunnel_is_up.get(("127.0.0.1", ssh_port)):
            context.log.info("Restarting SSH tunnel")
            ssh_tunnel.restart()
        else:
            context.log.info("Starting SSH tunnel")
            ssh_tunnel.start()

        try:
            for asset in target_assets:
                count = get_asset_count(asset=asset, db=resources.db)
                context.log.debug(f"count: {count}")
                if count > 0:
                    pass
        finally:
            context.log.info("Stopping SSH tunnel")
            ssh_tunnel.stop()


__all__ = [test_dynamic_partition_sensor]
