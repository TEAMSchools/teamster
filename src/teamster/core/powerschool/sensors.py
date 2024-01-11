import pendulum
from dagster import (
    AssetsDefinition,
    MonthlyPartitionsDefinition,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    TimeWindow,
    sensor,
)
from sqlalchemy import text

from teamster.core.sqlalchemy.resources import OracleResource
from teamster.core.ssh.resources import SSHResource


def build_powerschool_sensor(
    name, asset_defs: list[AssetsDefinition], minimum_interval_seconds=None
):
    @sensor(
        name=name,
        minimum_interval_seconds=minimum_interval_seconds,
        asset_selection=asset_defs,
    )
    def _sensor(
        context: SensorEvaluationContext,
        ssh_powerschool: SSHResource,
        db_powerschool: OracleResource,
    ):
        run_requests = []

        now = pendulum.now()

        ssh_tunnel = ssh_powerschool.get_tunnel(remote_port=1521, local_port=1521)

        try:
            ssh_tunnel.start()

            for asset in asset_defs:
                context.log.info(asset.key)

                partition_column = asset.metadata_by_key[asset.key]["partition_column"]

                latest_materialization_event = (
                    context.instance.get_latest_materialization_event(asset.key)
                )

                latest_materialization_timestamp = (
                    latest_materialization_event.asset_materialization.metadata.get(
                        "latest_materialization_timestamp"
                    )
                    if latest_materialization_event is not None
                    else None
                )

                latest_materialization_datetime = pendulum.from_timestamp(
                    timestamp=(
                        latest_materialization_timestamp.value
                        if latest_materialization_timestamp is not None
                        else 0.0
                    )  # type: ignore
                )

                window_start_fmt = latest_materialization_datetime.format(
                    "YYYY-MM-DDTHH:mm:ss.SSSSSS"
                )

                [(count,)] = db_powerschool.engine.execute_query(
                    query=text(
                        # trunk-ignore(bandit/B608)
                        "SELECT COUNT(*) "
                        f"FROM {asset.key.path[-1]} "
                        f"WHERE {partition_column} >= "
                        f"TO_TIMESTAMP('{window_start_fmt}', "
                        "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
                    ),
                    partition_size=1,
                    output_format=None,
                    call_timeout=10000,
                )  # type: ignore

                context.log.info(f"count: {count}")

                if int(count) > 0:
                    if isinstance(asset.partitions_def, MonthlyPartitionsDefinition):
                        partition_keys = (
                            asset.partitions_def.get_partition_keys_in_time_window(
                                time_window=TimeWindow(
                                    start=latest_materialization_datetime.start_of(
                                        "month"
                                    ),
                                    end=now.end_of("month"),
                                )
                            )
                        )
                    else:
                        partition_keys = [asset.partitions_def.get_last_partition_key()]

                    context.log.info(partition_keys)

                    hour_ts = now.start_of("hour").timestamp()

                    run_requests.extend(
                        [
                            RunRequest(
                                run_key=f"{asset.key.to_python_identifier()}_{partition_key}_{hour_ts}",
                                asset_selection=[asset.key],
                                partition_key=partition_key,
                            )
                            for partition_key in partition_keys
                        ]
                    )
        except Exception as e:
            return SensorResult(skip_reason=str(e))
        finally:
            ssh_tunnel.stop()

        return SensorResult(run_requests=run_requests)

    return _sensor
