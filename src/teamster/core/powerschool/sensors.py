import json

import pendulum
from dagster import (
    AssetsDefinition,
    AssetSelection,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    sensor,
)
from sqlalchemy import text

from teamster.core.sqlalchemy.resources import OracleResource
from teamster.core.ssh.resources import SSHConfigurableResource


def build_partition_sensor(
    name, asset_defs: list[AssetsDefinition], timezone, minimum_interval_seconds=None
):
    @sensor(
        name=name,
        minimum_interval_seconds=minimum_interval_seconds,
        asset_selection=AssetSelection.assets(*asset_defs),
    )
    def _sensor(
        context: SensorEvaluationContext,
        ssh_powerschool: SSHConfigurableResource,
        db_powerschool: OracleResource,
    ):
        cursor = json.loads(context.cursor or "{}")

        now = pendulum.now(timezone).start_of("minute")

        ssh_tunnel = ssh_powerschool.get_tunnel(remote_port=1521, local_port=1521)

        try:
            context.log.info("Starting SSH tunnel")
            ssh_tunnel.start()

            run_requests = []
            for asset in asset_defs:
                asset_key = asset.key
                last_partition_key = asset.partitions_def.get_last_partition_key()

                partition_column = asset.metadata_by_key[asset_key]["partition_column"]

                asset_key_string = asset_key.to_python_identifier()
                context.log.info(asset_key_string)

                table_name = asset_key.path[-1]

                for partition_key in asset.partitions_def.get_partition_keys():
                    is_requested = False
                    cursor_key = f"{asset_key_string}__{partition_key}"

                    last_updated = pendulum.from_timestamp(
                        cursor.get(cursor_key, 0), tz=timezone
                    )

                    asset.partitions_def.get_last_partition_key()
                    if last_updated.timestamp() == 0:
                        is_requested = True
                    elif partition_key != last_partition_key:
                        continue
                    else:
                        window_start = last_updated.format("YYYY-MM-DDTHH:mm:ss.SSSSSS")

                        context.log.info(partition_key)
                        window_end = (
                            pendulum.from_format(
                                string=partition_key,
                                fmt="YYYY-MM-DDTHH:mm:ssZZ",
                                tz=timezone,
                            )
                            .add(years=1)
                            .subtract(days=1)
                            .format("YYYY-MM-DDTHH:mm:ss.SSSSSS")
                        )

                        [(count,)] = db_powerschool.engine.execute_query(
                            query=text(
                                "SELECT COUNT(*) "
                                f"FROM {table_name} "
                                f"WHERE {partition_column} BETWEEN "
                                f"TO_TIMESTAMP('{window_start}', "
                                "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6') AND "
                                f"TO_TIMESTAMP('{window_end}', "
                                "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
                            ),
                            partition_size=1,
                            output_format=None,
                        )

                        context.log.info(f"count: {count}")

                        if count > 0:
                            is_requested = True

                    if is_requested:
                        run_requests.append(
                            RunRequest(
                                run_key=f"{asset_key_string}_{partition_key}",
                                asset_selection=[asset_key],
                                partition_key=partition_key,
                            )
                        )

                        cursor[cursor_key] = now.timestamp()

        finally:
            context.log.info("Stopping SSH tunnel")
            ssh_tunnel.stop()

        context.log.info(cursor)
        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))

    return _sensor
