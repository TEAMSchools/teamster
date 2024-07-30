import pendulum
from dagster import (
    MAX_RUNTIME_SECONDS_TAG,
    AssetMaterialization,
    AssetsDefinition,
    EventLogEntry,
    MonthlyPartitionsDefinition,
    PartitionsDefinition,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    SkipReason,
    TimeWindow,
    _check,
    sensor,
)
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sshtunnel import HandlerSSHTunnelForwarderError

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
    ) -> SensorResult | SkipReason:
        now = pendulum.now()

        run_requests = []

        ssh_tunnel = ssh_powerschool.get_tunnel(remote_port=1521, local_port=1521)

        try:
            ssh_tunnel.start()
        except HandlerSSHTunnelForwarderError as e:
            if "An error occurred while opening tunnels." in e.args:
                return SkipReason(str(e))
            else:
                raise e
        except Exception as e:
            context.log.error(msg=str(e))
            raise e

        for asset in asset_defs:
            asset_key_identifier = asset.key.to_python_identifier()

            if isinstance(asset.partitions_def, MonthlyPartitionsDefinition):
                partition_keys = asset.partitions_def.get_partition_keys_in_time_window(
                    time_window=TimeWindow(
                        start=latest_materialization_datetime.start_of("month"),
                        end=now.end_of("month"),
                    )
                )
            elif isinstance(asset.partitions_def, PartitionsDefinition):
                partition_keys = [asset.partitions_def.get_last_partition_key()]
            else:
                partition_keys = []

            latest_materialization_event = (
                context.instance.get_latest_materialization_event(asset.key)
            )

            if latest_materialization_event is None:
                run_requests.extend(
                    [
                        RunRequest(
                            run_key=(
                                f"{asset_key_identifier}_"
                                f"{partition_key}_"
                                f"{now.timestamp()}"
                            ),
                            asset_selection=[asset.key],
                            partition_key=partition_key,
                            tags={MAX_RUNTIME_SECONDS_TAG: max_runtime_seconds},
                        )
                        for partition_key in partition_keys
                    ]
                )

            asset_materialization = _check.not_none(
                value=latest_materialization_event.asset_materialization
            )

            latest_materialization_timestamp = asset_materialization.metadata.get(
                "latest_materialization_timestamp"
            )

            records = _check.inst(
                obj=asset_materialization.metadata.get("records"), ttype=int
            )

            latest_materialization_datetime = pendulum.from_timestamp(
                timestamp=(
                    _check.inst(latest_materialization_timestamp.value, float)
                    if latest_materialization_timestamp is not None
                    else 0.0
                )
            )

            latest_materialization_fmt = latest_materialization_datetime.in_timezone(
                tz=execution_timezone
            ).format("YYYY-MM-DDTHH:mm:ss.SSSSSS")

            try:
                [(modified_count,)] = _check.inst(
                    db_powerschool.engine.execute_query(
                        query=text(
                            f"SELECT COUNT(*) FROM {asset.key.path[-1]} "
                            f"WHERE {asset.metadata_by_key[asset.key]["partition_column"]} >= "
                            f"TO_TIMESTAMP('{latest_materialization_fmt}', "
                            "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
                        ),
                        partition_size=1,
                        output_format=None,
                    ),
                    list,
                )

                [(partition_count,)] = _check.inst(
                    db_powerschool.engine.execute_query(
                        query=text(
                            f"SELECT COUNT(*) FROM {asset.key.path[-1]} "
                            f"WHERE {asset.metadata_by_key[asset.key]["partition_column"]} >= "
                            f"TO_TIMESTAMP('{latest_materialization_fmt}', "
                            "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
                        ),
                        partition_size=1,
                        output_format=None,
                    ),
                    list,
                )
            except OperationalError as e:
                if "DPY-6003" in str(e):
                    context.log.error(msg=str(e))
                    return SkipReason(str(e))
                else:
                    raise e
            except Exception as e:
                context.log.error(msg=str(e))
                raise e

            if modified_count > 0:
                context.log.info(asset.key)
                context.log.info(f"modified_count: {modified_count}")

                context.log.info(partition_keys)

                run_requests.extend(
                    [
                        RunRequest(
                            run_key=(
                                f"{asset_key_identifier}_"
                                f"{partition_key}_"
                                f"{now.timestamp()}"
                            ),
                            asset_selection=[asset.key],
                            partition_key=partition_key,
                            tags={MAX_RUNTIME_SECONDS_TAG: max_runtime_seconds},
                        )
                        for partition_key in partition_keys
                    ]
                )

        ssh_tunnel.stop()

        return SensorResult(run_requests=run_requests)

    return _sensor


def build_powerschool_partitioned_asset_count_sensor(
    name,
    asset_selection: list[AssetsDefinition],
    max_runtime_seconds,
    minimum_interval_seconds=None,
):
    @sensor(
        name=name,
        asset_selection=asset_selection,
        minimum_interval_seconds=minimum_interval_seconds,
    )
    def _sensor(
        context: SensorEvaluationContext,
        ssh_powerschool: SSHResource,
        db_powerschool: OracleResource,
    ) -> SensorResult | SkipReason:
        now_timestamp = pendulum.now().timestamp()

        run_requests = []

        ssh_tunnel = ssh_powerschool.get_tunnel(remote_port=1521, local_port=1521)

        try:
            ssh_tunnel.start()
        except HandlerSSHTunnelForwarderError as e:
            if "An error occurred while opening tunnels." in e.args:
                return SkipReason(str(e))
            else:
                raise e
        except Exception as e:
            context.log.error(msg=str(e))
            raise e

        for asset in asset_selection:
            context.log.info(asset.key)

            partition_column = asset.metadata_by_key[asset.key]["partition_column"]
            partitions_def = _check.not_none(value=asset.partitions_def)

            last_partition_key = _check.not_none(
                value=partitions_def.get_last_partition_key()
            )

            last_partition_key_fmt = pendulum.from_format(
                string=last_partition_key, fmt="YYYY-MM-DDTHH:mm:ssZZ"
            ).format("YYYY-MM-DDTHH:mm:ss.SSSSSS")

            latest_materialization_event = _check.inst(
                context.instance.get_latest_materialization_event(asset.key),
                EventLogEntry,
            )

            asset_materialization = _check.inst(
                obj=latest_materialization_event.asset_materialization,
                ttype=AssetMaterialization,
            )

            records = _check.inst(
                obj=asset_materialization.metadata["records"], ttype=int
            )

            query = text(
                # trunk-ignore(bandit/B608)
                f"SELECT COUNT(*) FROM {asset.key.path[-1]} "
                f"WHERE {partition_column} >= "
                f"TO_TIMESTAMP('{last_partition_key_fmt}', "
                "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
            )

            try:
                [(count,)] = _check.inst(
                    db_powerschool.engine.execute_query(
                        query=query, partition_size=1, output_format=None
                    ),
                    list,
                )
            except OperationalError as e:
                if "DPY-6003" in str(e):
                    context.log.error(msg=str(e))
                    return SkipReason(str(e))
                else:
                    raise e
            except Exception as e:
                context.log.error(msg=str(e))
                raise e

            context.log.info(f"count: {count}")

            if int(count) > records:
                run_requests.append(
                    RunRequest(
                        run_key=(
                            f"{asset.key.to_python_identifier()}_{last_partition_key}_"
                            f"{now_timestamp}"
                        ),
                        asset_selection=[asset.key],
                        partition_key=last_partition_key,
                        tags={MAX_RUNTIME_SECONDS_TAG: max_runtime_seconds},
                    )
                )

        ssh_tunnel.stop()

        return SensorResult(run_requests=run_requests)

    return _sensor
