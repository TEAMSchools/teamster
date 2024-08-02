from collections import defaultdict
from itertools import groupby
from operator import itemgetter

import pendulum
from dagster import (
    AssetKey,
    AssetsDefinition,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    SkipReason,
    _check,
    define_asset_job,
    sensor,
)
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sshtunnel import HandlerSSHTunnelForwarderError

from teamster.libraries.sqlalchemy.resources import OracleResource
from teamster.libraries.ssh.resources import SSHResource


def get_query_text(table: str, column: str, value: str | None):
    if value is None:
        # trunk-ignore(bandit/B608)
        query = f"SELECT COUNT(*) FROM {table}"
    else:
        query = (
            # trunk-ignore(bandit/B608)
            f"SELECT COUNT(*) FROM {table} WHERE "
            f"{column} >= TO_TIMESTAMP('{value}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
        )

    return text(query)


def build_powerschool_asset_sensor(
    code_location,
    asset_selection: list[AssetsDefinition],
    execution_timezone,
    minimum_interval_seconds=None,
):
    jobs = []
    keys_by_partitions_def = defaultdict(set[AssetKey])

    base_job_name = f"{code_location}_powerschool_sis_asset_job"

    asset_keys = [a.key for a in asset_selection]

    for assets_def in asset_selection:
        keys_by_partitions_def[assets_def.partitions_def].add(assets_def.key)

    for partitions_def, keys in keys_by_partitions_def.items():
        if partitions_def is None:
            job_name = f"{base_job_name}_None"
        else:
            job_name = (
                f"{base_job_name}_{partitions_def.get_serializable_unique_identifier()}"
            )

        jobs.append(define_asset_job(name=job_name, selection=list(keys)))

    @sensor(
        name=f"{base_job_name}_sensor",
        jobs=jobs,
        minimum_interval_seconds=minimum_interval_seconds,
    )
    def _sensor(
        context: SensorEvaluationContext,
        ssh_powerschool: SSHResource,
        db_powerschool: OracleResource,
    ) -> SensorResult | SkipReason:
        now_timestamp = pendulum.now().timestamp()

        run_requests = []
        run_request_kwargs = []

        latest_materialization_events = (
            context.instance.get_latest_materialization_events(asset_keys)
        )

        ssh_tunnel = ssh_powerschool.get_tunnel(remote_port=1521, local_port=1521)

        try:
            ssh_tunnel.start()
        except HandlerSSHTunnelForwarderError as e:
            if "An error occurred while opening tunnels." in e.args:
                return SkipReason(str(e))
            else:
                raise e

        for asset in asset_selection:
            asset_key_identifier = asset.key.to_python_identifier()
            metadata = asset.metadata_by_key[asset.key]
            latest_materialization_event = latest_materialization_events.get(asset.key)

            table_name = metadata["table_name"]
            partition_column = metadata["partition_column"]

            if asset.partitions_def is not None:
                partition_key = _check.not_none(
                    value=asset.partitions_def.get_last_partition_key()
                )

                partition_key_fmt = pendulum.from_format(
                    string=partition_key, fmt="YYYY-MM-DDTHH:mm:ssZZ"
                ).format("YYYY-MM-DDTHH:mm:ss.SSSSSS")

                job_name = (
                    f"{base_job_name}_"
                    f"{asset.partitions_def.get_serializable_unique_identifier()}"
                )
            else:
                partition_key_fmt = partition_key = None
                job_name = f"{base_job_name}_None"

            # request run if asset never materialized
            if latest_materialization_event is None:
                context.log.info(msg=f"{asset_key_identifier} never materialized")
                run_request_kwargs.append(
                    {
                        "asset_key": asset.key,
                        "job_name": job_name,
                        "partition_key": partition_key,
                    }
                )

                continue

            asset_materialization = _check.not_none(
                value=latest_materialization_event.asset_materialization
            )

            # request run if latest partition not materialized
            if (
                partition_key is not None
                and partition_key != asset_materialization.partition
            ):
                context.log.info(
                    msg=f"{asset_key_identifier}\n{partition_key} never materialized"
                )
                run_request_kwargs.append(
                    {
                        "asset_key": asset.key,
                        "job_name": job_name,
                        "partition_key": partition_key,
                    }
                )

                continue

            record_count = asset_materialization.metadata["records"].value

            if asset.partitions_def is not None:
                timestamp = _check.inst(
                    obj=asset_materialization.metadata[
                        "latest_materialization_timestamp"
                    ].value,
                    ttype=float,
                )

                timestamp_fmt = pendulum.from_timestamp(
                    timestamp=timestamp, tz=execution_timezone
                ).format("YYYY-MM-DDTHH:mm:ss.SSSSSS")
            else:
                timestamp_fmt = None

            try:
                if timestamp_fmt is None:
                    modified_count = 0
                else:
                    [(modified_count,)] = _check.inst(
                        db_powerschool.execute_query(
                            query=get_query_text(
                                table=table_name,
                                column=partition_column,
                                value=timestamp_fmt,
                            ),
                            partition_size=1,
                            prefetch_rows=1,
                            array_size=1,
                        ),
                        list,
                    )

                [(partition_count,)] = _check.inst(
                    db_powerschool.execute_query(
                        query=get_query_text(
                            table=table_name,
                            column=partition_column,
                            value=partition_key_fmt,
                        ),
                        partition_size=1,
                        prefetch_rows=1,
                        array_size=1,
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

            if modified_count > 0 or partition_count != record_count:
                context.log.info(
                    msg=(
                        f"{asset_key_identifier}\n{partition_key}\n"
                        f"modified count ({modified_count}) > 0 OR "
                        f"partition count ({partition_count}) "
                        f"!= {record_count}"
                    )
                )

                run_request_kwargs.append(
                    {
                        "asset_key": asset.key,
                        "job_name": job_name,
                        "partition_key": partition_key,
                    }
                )

        ssh_tunnel.stop()

        for (job_name, parition_key), group in groupby(
            iterable=run_request_kwargs, key=itemgetter("job_name", "partition_key")
        ):
            run_requests.append(
                RunRequest(
                    run_key=f"{job_name}_{parition_key}_{now_timestamp}",
                    job_name=job_name,
                    partition_key=parition_key,
                    asset_selection=[g["asset_key"] for g in group],
                )
            )

        return SensorResult(run_requests=run_requests)

    return _sensor
