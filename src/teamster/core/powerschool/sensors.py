import json

import pendulum
from dagster import (
    AddDynamicPartitionsRequest,
    AssetsDefinition,
    AssetSelection,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    sensor,
)
from sqlalchemy import text

from teamster.core.utils.variables import LOCAL_TIME_ZONE

# import os


def get_asset_count(asset, db, window_start):
    partition_column = asset.metadata_by_key[asset.key]["partition_column"]
    window_start_fmt = window_start.format("YYYY-MM-DDTHH:mm:ss.SSSSSS")

    query = text(
        text=" ".join(
            [
                "SELECT COUNT(*)",
                f"FROM {asset.asset_key.path[-1]}",
                f"WHERE {partition_column} >=",
                f"TO_TIMESTAMP('{window_start_fmt}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')",
            ]
        )
    )

    [(count,)] = db.execute_query(query=query, partition_size=1, output=None)

    return count


def build_dynamic_partition_sensor(
    code_location,
    name,
    asset_defs: list[AssetsDefinition],
    minimum_interval_seconds=None,
):
    @sensor(
        name=name,
        minimum_interval_seconds=minimum_interval_seconds,
        asset_selection=AssetSelection.assets(*asset_defs),
        required_resource_keys={"ps_ssh", "ps_db"},
    )
    def _sensor(context: SensorEvaluationContext):
        cursor = json.loads(context.cursor or "{}")

        window_end = (
            pendulum.now(tz=LOCAL_TIME_ZONE)
            .subtract(minutes=1)  # 1 min grace period for PS lag
            .start_of("minute")
        )

        # ssh_port = 1521
        # ssh_tunnel = context.resources.ps_ssh.get_tunnel(
        #     remote_port=ssh_port,
        #     remote_host=os.getenv(f"{code_location.upper()}_PS_SSH_REMOTE_BIND_HOST"),
        #     local_port=ssh_port,
        # )

        # ssh_tunnel.check_tunnels()
        # if ssh_tunnel.tunnel_is_up.get(("127.0.0.1", ssh_port)):
        #     context.log.debug("Restarting SSH tunnel")
        #     ssh_tunnel.restart()
        # else:
        #     context.log.debug("Starting SSH tunnel")
        #     ssh_tunnel.start()

        # try:
        run_requests = []
        dynamic_partitions_requests = []

        for asset in asset_defs:
            run_request = False

            asset_key_string = asset.key.to_python_identifier()
            context.log.debug(asset_key_string)

            cursor_window_start = cursor.get(asset_key_string)

            if (
                not context.instance.get_latest_materialization_event(asset.key)
                or cursor_window_start is None
            ):
                window_start = pendulum.from_timestamp(0)
                run_request = True
                run_config = {
                    "execution": {
                        "config": {
                            "resources": {"limits": {"cpu": "750m", "memory": "1.0Gi"}}
                        }
                    }
                }
            else:
                window_start = pendulum.from_timestamp(
                    cursor_window_start, tz=LOCAL_TIME_ZONE
                )

                count = get_asset_count(
                    asset=asset,
                    db=context.resources.ps_db,
                    window_start=window_start,
                )

                context.log.debug(f"count: {count}")

                if count > 0:
                    run_request = True
                    run_config = None

            if run_request:
                partition_key = window_start.to_iso8601_string()

                dynamic_partitions_requests.append(
                    AddDynamicPartitionsRequest(
                        partitions_def_name=asset.partitions_def.name,
                        partition_keys=[partition_key],
                    ),
                )

                run_requests.append(
                    RunRequest(
                        run_key="_".join(
                            [
                                asset.key.to_python_identifier(),
                                str(window_start.timestamp()),
                            ]
                        ),
                        run_config=run_config,
                        asset_selection=[asset.key],
                        partition_key=partition_key,
                    )
                )

                cursor[asset_key_string] = window_end.timestamp()
        # finally:
        #     context.log.debug("Stopping SSH tunnel")
        #     ssh_tunnel.stop()

        return SensorResult(
            run_requests=run_requests,
            cursor=json.dumps(cursor),
            dynamic_partitions_requests=dynamic_partitions_requests,
        )

    return _sensor
