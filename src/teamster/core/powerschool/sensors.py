import json

import pendulum
from dagster import (
    AssetsDefinition,
    AssetSelection,
    MonthlyPartitionsDefinition,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    sensor,
)
from sqlalchemy import text

from teamster.core.sqlalchemy.resources import OracleResource
from teamster.core.ssh.resources import SSHResource
from teamster.core.utils.classes import FiscalYearPartitionsDefinition


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
        ssh_powerschool: SSHResource,
        db_powerschool: OracleResource,
    ):
        now = pendulum.now(timezone).start_of("minute")
        cursor = json.loads(context.cursor or "{}")

        ssh_tunnel = ssh_powerschool.get_tunnel(remote_port=1521, local_port=1521)

        try:
            context.log.info("Starting SSH tunnel")
            ssh_tunnel.start()

            run_requests = []
            for asset in asset_defs:
                is_requested = False

                asset_key_string = asset.key.to_python_identifier()
                partition_key = asset.partitions_def.get_last_partition_key()
                partition_column = asset.metadata_by_key[asset.key]["partition_column"]

                context.log.info(asset_key_string)

                last_updated = pendulum.from_timestamp(
                    cursor.get(asset_key_string, 0), tz=timezone
                )

                if last_updated.timestamp() == 0:
                    is_requested = True
                else:
                    context.log.info(partition_key)

                    window_start_fmt = last_updated.format("YYYY-MM-DDTHH:mm:ss.SSSSSS")

                    if isinstance(
                        asset.partitions_def,
                        FiscalYearPartitionsDefinition,
                    ):
                        window_end_fmt = (
                            last_updated.add(years=1)
                            .subtract(days=1)
                            .end_of("day")
                            .format("YYYY-MM-DDTHH:mm:ss.SSSSSS")
                        )
                    elif isinstance(
                        asset.partitions_def,
                        MonthlyPartitionsDefinition,
                    ):
                        window_end_fmt = last_updated.end_of("month").format(
                            "YYYY-MM-DDTHH:mm:ss.SSSSSS"
                        )

                    [(count,)] = db_powerschool.engine.execute_query(
                        query=text(
                            "SELECT COUNT(*) "
                            f"FROM {asset.key.path[-1]} "
                            f"WHERE {partition_column} BETWEEN "
                            f"TO_TIMESTAMP('{window_start_fmt}', "
                            "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6') AND "
                            f"TO_TIMESTAMP('{window_end_fmt}', "
                            "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
                        ),
                        partition_size=1,
                        output_format=None,
                    )

                    context.log.info(f"count: {count}")

                    if count > 0:
                        is_requested = True

                if is_requested:
                    hour_ts = now.start_of("hour").timestamp()

                    run_requests.append(
                        RunRequest(
                            run_key=f"{asset_key_string}_{hour_ts}",
                            asset_selection=[asset.key],
                            partition_key=partition_key,
                        )
                    )

                    cursor[asset_key_string] = hour_ts
        finally:
            context.log.info("Stopping SSH tunnel")
            ssh_tunnel.stop()

        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))

    return _sensor
