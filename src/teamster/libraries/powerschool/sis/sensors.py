import pendulum
from dagster import (
    MAX_RUNTIME_SECONDS_TAG,
    AssetKey,
    AssetMaterialization,
    AssetsDefinition,
    EventLogEntry,
    MonthlyPartitionsDefinition,
    PartitionsDefinition,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    TimeWindow,
    _check,
    sensor,
)
from sqlalchemy import text
from sshtunnel import SSHTunnelForwarder

from teamster.libraries.sqlalchemy.resources import OracleResource
from teamster.libraries.ssh.resources import SSHResource


def build_powerschool_sensor(
    name,
    asset_selection: list[AssetsDefinition],
    asset_defs: list[AssetsDefinition],
    execution_timezone,
    max_runtime_seconds,
    minimum_interval_seconds=None,
):
    @sensor(
        name=name,
        minimum_interval_seconds=minimum_interval_seconds,
        asset_selection=asset_selection,
    )
    def _sensor(
        context: SensorEvaluationContext,
        ssh_powerschool: SSHResource,
        db_powerschool: OracleResource,
    ):
        run_requests = []

        now = pendulum.now()

        try:
            with ssh_powerschool.get_tunnel(
                remote_port=1521, local_port=1521
            ) as ssh_tunnel:
                ssh_tunnel = _check.inst(ssh_tunnel, SSHTunnelForwarder)

                ssh_tunnel.start()

                for asset in asset_defs:
                    context.log.info(asset.key)

                    table_name = asset.key.path[-1]
                    partition_column = asset.metadata_by_key[asset.key][
                        "partition_column"
                    ]

                    latest_materialization_event = _check.inst(
                        context.instance.get_latest_materialization_event(asset.key),
                        EventLogEntry,
                    )

                    asset_materialization = _check.inst(
                        latest_materialization_event.asset_materialization,
                        AssetMaterialization,
                    )

                    latest_materialization_timestamp = (
                        asset_materialization.metadata.get(
                            "latest_materialization_timestamp"
                        )
                        if latest_materialization_event is not None
                        else None
                    )

                    latest_materialization_datetime = pendulum.from_timestamp(
                        timestamp=(
                            _check.inst(latest_materialization_timestamp.value, float)
                            if latest_materialization_timestamp is not None
                            else 0.0
                        )
                    )

                    latest_materialization_fmt = (
                        latest_materialization_datetime.in_timezone(
                            tz=execution_timezone
                        ).format("YYYY-MM-DDTHH:mm:ss.SSSSSS")
                    )

                    [(count,)] = _check.inst(
                        db_powerschool.engine.execute_query(
                            query=text(
                                # trunk-ignore(bandit/B608)
                                f"SELECT COUNT(*) FROM {table_name} "
                                f"WHERE {partition_column} >= "
                                f"TO_TIMESTAMP('{latest_materialization_fmt}', "
                                "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
                            ),
                            partition_size=1,
                            output_format=None,
                        ),
                        list,
                    )

                    context.log.info(f"count: {count}")

                    if int(count) > 0:
                        if isinstance(
                            asset.partitions_def, MonthlyPartitionsDefinition
                        ):
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
                        elif isinstance(asset.partitions_def, PartitionsDefinition):
                            partition_keys = [
                                asset.partitions_def.get_last_partition_key()
                            ]
                        else:
                            partition_keys = []

                        context.log.info(partition_keys)

                        hour_ts = now.start_of("hour").timestamp()

                        run_requests.extend(
                            [
                                RunRequest(
                                    run_key=f"{asset.key.to_python_identifier()}_{partition_key}_{hour_ts}",
                                    asset_selection=[asset.key],
                                    partition_key=partition_key,
                                    tags={MAX_RUNTIME_SECONDS_TAG: max_runtime_seconds},
                                )
                                for partition_key in partition_keys
                            ]
                        )

                        if table_name == "storedgrades":
                            run_requests.append(
                                RunRequest(
                                    run_key=f"storedgrades_dcid_{hour_ts}",
                                    asset_selection=[
                                        AssetKey(
                                            [*asset.key.path[:-1], "storedgrades_dcid"]
                                        )
                                    ],
                                    tags={MAX_RUNTIME_SECONDS_TAG: max_runtime_seconds},
                                )
                            )

            return SensorResult(run_requests=run_requests)
        except Exception as e:
            return SensorResult(skip_reason=str(e))

    return _sensor
