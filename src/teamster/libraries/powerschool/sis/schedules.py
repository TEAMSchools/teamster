from itertools import groupby
from operator import itemgetter

import pendulum
from dagster import (
    MAX_RUNTIME_SECONDS_TAG,
    AssetsDefinition,
    DagsterEventType,
    EventRecordsFilter,
    MonthlyPartitionsDefinition,
    RunRequest,
    ScheduleEvaluationContext,
    _check,
    schedule,
)
from sqlalchemy import text

from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.powerschool.sis.resources import PowerSchoolODBCResource
from teamster.libraries.ssh.resources import SSHResource


def get_query_text(
    table: str,
    column: str | None,
    start_value: str | None = None,
    end_value: str | None = None,
):
    if column is None:
        query = f"SELECT COUNT(*) FROM {table}"
    elif end_value is None:
        query = (
            f"SELECT COUNT(*) FROM {table} "
            f"WHERE {column} >= "
            f"TO_TIMESTAMP('{start_value}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
        )
    else:
        query = (
            f"SELECT COUNT(*) FROM {table} "
            f"WHERE {column} BETWEEN "
            f"TO_TIMESTAMP('{start_value}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6') AND "
            f"TO_TIMESTAMP('{end_value}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
        )

    return text(query)


def build_powerschool_sis_asset_schedule(
    code_location,
    asset_selection: list[AssetsDefinition],
    cron_schedule,
    execution_timezone,
):
    asset_keys = [a.key for a in asset_selection]

    @schedule(
        name=f"{code_location}__powerschool__sis__asset_job_schedule",
        cron_schedule=cron_schedule,
        execution_timezone=execution_timezone,
        target=asset_selection,
    )
    def _schedule(
        context: ScheduleEvaluationContext,
        ssh_powerschool: SSHResource,
        db_powerschool: PowerSchoolODBCResource,
    ):
        run_request_kwargs = []

        latest_materialization_events = (
            context.instance.get_latest_materialization_events(asset_keys)
        )

        ssh_tunnel = ssh_powerschool.get_tunnel(remote_port=1521, local_port=1521)

        try:
            ssh_tunnel.start()
        except Exception as e:
            ssh_tunnel.stop()
            raise e

        for asset in asset_selection:
            asset_key_identifier = asset.key.to_python_identifier()
            metadata = asset.metadata_by_key[asset.key]

            table_name = metadata["table_name"]
            partition_column = metadata["partition_column"]

            # non-partitioned assets
            if asset.partitions_def is None:
                latest_materialization_event = latest_materialization_events.get(
                    asset.key
                )

                # request run if asset never materialized
                if latest_materialization_event is None:
                    context.log.info(msg=f"{asset_key_identifier} never materialized")
                    run_request_kwargs.append(
                        {"key": asset.key, "partitions_def": "", "partition_key": ""}
                    )
                    continue

                metadata = _check.not_none(
                    value=latest_materialization_event.asset_materialization
                ).metadata

                materialization_count = metadata["records"].value

                # request run if table modified count > 0
                if partition_column is not None:
                    timestamp = _check.inst(
                        obj=metadata["latest_materialization_timestamp"].value,
                        ttype=float,
                    )

                    timestamp_fmt = pendulum.from_timestamp(
                        timestamp=timestamp, tz=execution_timezone
                    ).format("YYYY-MM-DDTHH:mm:ss.SSSSSS")

                    [(modified_count,)] = _check.inst(
                        db_powerschool.execute_query(
                            query=get_query_text(
                                table=table_name,
                                column=partition_column,
                                start_value=timestamp_fmt,
                            ),
                            prefetch_rows=2,
                            array_size=1,
                        ),
                        list,
                    )

                    if modified_count > 0:
                        context.log.info(
                            msg=(
                                f"{asset_key_identifier}\n"
                                f"modified count: {modified_count}"
                            )
                        )
                        run_request_kwargs.append(
                            {
                                "key": asset.key,
                                "partitions_def": "",
                                "partition_key": "",
                            }
                        )
                        continue

                # request run if table count doesn't match latest materialization
                [(table_count,)] = _check.inst(
                    db_powerschool.execute_query(
                        query=get_query_text(table=table_name, column=None),
                        prefetch_rows=2,
                        array_size=1,
                    ),
                    list,
                )

                if table_count != materialization_count:
                    context.log.info(
                        msg=(
                            f"{asset_key_identifier}\n"
                            f"PS count ({table_count}) != "
                            f"DB count ({materialization_count})"
                        )
                    )
                    run_request_kwargs.append(
                        {"key": asset.key, "partitions_def": "", "partition_key": ""}
                    )
                    continue
            # partitioned assets
            else:
                first_partition_key = asset.partitions_def.get_first_partition_key()
                last_partition_key = asset.partitions_def.get_last_partition_key()
                partition_keys = asset.partitions_def.get_partition_keys()
                partitions_def_identifier = (
                    asset.partitions_def.get_serializable_unique_identifier()
                )

                if isinstance(asset.partitions_def, FiscalYearPartitionsDefinition):
                    date_add_kwargs = {"years": 1}
                elif isinstance(asset.partitions_def, MonthlyPartitionsDefinition):
                    date_add_kwargs = {"months": 1}
                    partition_keys = partition_keys[-12:]  # limit to 12 months
                else:
                    date_add_kwargs = {}

                for partition_key in partition_keys:
                    event_record = context.instance.get_event_records(
                        event_records_filter=EventRecordsFilter(
                            event_type=DagsterEventType.ASSET_MATERIALIZATION,
                            asset_key=asset.key,
                            asset_partitions=[partition_key],
                        ),
                        limit=1,
                    )

                    # request run if partition never materialized
                    if not event_record:
                        context.log.info(
                            msg=f"{asset_key_identifier} never materialized"
                        )
                        run_request_kwargs.append(
                            {
                                "key": asset.key,
                                "partitions_def": partitions_def_identifier,
                                "partition_key": partition_key,
                            }
                        )
                        continue

                    metadata = _check.not_none(
                        value=event_record[0].asset_materialization
                    ).metadata

                    # skip first partition
                    # TODO: handle checking for null values in partition key
                    if partition_key == first_partition_key:
                        continue

                    # request run if last partition modified count > 0
                    if partition_key == last_partition_key:
                        timestamp = _check.inst(
                            obj=metadata["latest_materialization_timestamp"].value,
                            ttype=float,
                        )

                        timestamp_fmt = pendulum.from_timestamp(
                            timestamp=timestamp, tz=execution_timezone
                        ).format("YYYY-MM-DDTHH:mm:ss.SSSSSS")

                        [(modified_count,)] = _check.inst(
                            db_powerschool.execute_query(
                                query=get_query_text(
                                    table=table_name,
                                    column=partition_column,
                                    start_value=timestamp_fmt,
                                ),
                                prefetch_rows=2,
                                array_size=1,
                            ),
                            list,
                        )

                        if modified_count > 0:
                            context.log.info(
                                msg=(
                                    f"{asset_key_identifier}\n{partition_key}\n"
                                    f"modified count: {modified_count}"
                                )
                            )
                            run_request_kwargs.append(
                                {
                                    "key": asset.key,
                                    "partitions_def": partitions_def_identifier,
                                    "partition_key": partition_key,
                                }
                            )
                            continue

                    # request run if partition count != latest materialization
                    materialization_count = metadata["records"].value

                    partition_start = pendulum.from_format(
                        string=partition_key, fmt="YYYY-MM-DDTHH:mm:ssZZ"
                    )

                    partition_end = (
                        partition_start.add(**date_add_kwargs)
                        .subtract(days=1)
                        .end_of("day")
                    )

                    [(partition_count,)] = _check.inst(
                        db_powerschool.execute_query(
                            query=get_query_text(
                                table=table_name,
                                column=partition_column,
                                start_value=partition_start.format(
                                    "YYYY-MM-DDTHH:mm:ss.SSSSSS"
                                ),
                                end_value=partition_end.format(
                                    "YYYY-MM-DDTHH:mm:ss.SSSSSS"
                                ),
                            ),
                            prefetch_rows=2,
                            array_size=1,
                        ),
                        list,
                    )

                    if partition_count > 0 and partition_count != materialization_count:
                        context.log.info(
                            msg=(
                                f"{asset_key_identifier}\n{partition_key}\n"
                                f"PS count ({partition_count}) "
                                f"!= DB count ({materialization_count})"
                            )
                        )
                        run_request_kwargs.append(
                            {
                                "key": asset.key,
                                "partitions_def": partitions_def_identifier,
                                "partition_key": partition_key,
                            }
                        )
                        continue

        ssh_tunnel.stop()

        item_getter = itemgetter("partitions_def", "partition_key")

        for (partitions_def, partition_key), group in groupby(
            iterable=sorted(run_request_kwargs, key=item_getter), key=item_getter
        ):
            yield RunRequest(
                run_key=f"{partitions_def}_{partition_key}",
                asset_selection=[g["key"] for g in group],
                partition_key=partition_key,
                tags={MAX_RUNTIME_SECONDS_TAG: (10 * 60)},
            )

    return _schedule
