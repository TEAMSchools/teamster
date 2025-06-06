from datetime import datetime
from itertools import groupby
from operator import itemgetter
from zoneinfo import ZoneInfo

from dagster import (
    MAX_RUNTIME_SECONDS_TAG,
    AssetRecordsFilter,
    AssetsDefinition,
    MonthlyPartitionsDefinition,
    RunRequest,
    ScheduleEvaluationContext,
    schedule,
)
from dagster_shared import check
from dateutil.relativedelta import relativedelta

from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.powerschool.sis.resources import PowerSchoolODBCResource
from teamster.libraries.powerschool.sis.utils import get_query_text
from teamster.libraries.ssh.resources import SSHResource


def build_powerschool_sis_asset_schedule(
    code_location: str,
    execution_timezone: ZoneInfo,
    cron_schedule: str,
    asset_selection: list[AssetsDefinition],
    max_runtime_seconds: int = (60 * 10),
):
    asset_keys = [a.key for a in asset_selection]

    @schedule(
        name=f"{code_location}__powerschool__sis__asset_job_schedule",
        cron_schedule=cron_schedule,
        execution_timezone=str(execution_timezone),
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

        context.log.info(msg=f"Opening SSH tunnel to {ssh_powerschool.remote_host}")
        ssh_tunnel = ssh_powerschool.open_ssh_tunnel()

        try:
            connection = db_powerschool.connect()
        except Exception as e:
            ssh_tunnel.kill()
            raise e

        try:
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
                        context.log.info(
                            msg=f"{asset_key_identifier} never materialized"
                        )
                        run_request_kwargs.append(
                            {
                                "key": asset.key,
                                "partitions_def": "",
                                "partition_key": "",
                            }
                        )
                        continue

                    metadata = check.not_none(
                        value=latest_materialization_event.asset_materialization
                    ).metadata

                    materialization_count = metadata["records"].value

                    # request run if table modified count > 0
                    if partition_column is not None:
                        timestamp = check.inst(
                            obj=metadata["latest_materialization_timestamp"].value,
                            ttype=float,
                        )

                        timestamp_fmt = (
                            datetime.fromtimestamp(
                                timestamp=timestamp, tz=execution_timezone
                            )
                            .replace(tzinfo=None)
                            .isoformat(timespec="microseconds")
                        )

                        [(modified_count,)] = check.inst(
                            db_powerschool.execute_query(
                                connection=connection,
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
                    [(table_count,)] = check.inst(
                        db_powerschool.execute_query(
                            connection=connection,
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
                            {
                                "key": asset.key,
                                "partitions_def": "",
                                "partition_key": "",
                            }
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
                        event_records = context.instance.fetch_materializations(
                            records_filter=AssetRecordsFilter(
                                asset_key=asset.key, asset_partitions=[partition_key]
                            ),
                            limit=1,
                        )

                        # request run if partition never materialized
                        if not event_records.records:
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

                        metadata = check.not_none(
                            value=event_records.records[0].asset_materialization
                        ).metadata

                        # skip first partition
                        # TODO: handle checking for null values in partition key
                        if partition_key == first_partition_key:
                            continue

                        # request run if last partition modified count > 0
                        if partition_key == last_partition_key:
                            timestamp = check.inst(
                                obj=metadata["latest_materialization_timestamp"].value,
                                ttype=float,
                            )

                            timestamp_fmt = (
                                datetime.fromtimestamp(
                                    timestamp=timestamp, tz=execution_timezone
                                )
                                .replace(tzinfo=None)
                                .isoformat(timespec="microseconds")
                            )

                            [(modified_count,)] = check.inst(
                                db_powerschool.execute_query(
                                    connection=connection,
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
                        partition_start = datetime.fromisoformat(partition_key)

                        partition_end = (
                            partition_start
                            # trunk-ignore(pyright/reportArgumentType)
                            + relativedelta(**date_add_kwargs)
                            - relativedelta(days=1)
                        ).replace(hour=23, minute=59, second=59, microsecond=999999)

                        start_value = partition_start.replace(tzinfo=None).isoformat(
                            timespec="microseconds"
                        )
                        end_value = partition_end.replace(tzinfo=None).isoformat(
                            timespec="microseconds"
                        )

                        [(partition_count,)] = check.inst(
                            db_powerschool.execute_query(
                                connection=connection,
                                query=get_query_text(
                                    table=table_name,
                                    column=partition_column,
                                    start_value=start_value,
                                    end_value=end_value,
                                ),
                                prefetch_rows=2,
                                array_size=1,
                            ),
                            list,
                        )

                        materialization_count = metadata["records"].value

                        if (
                            partition_count > 0
                            and partition_count != materialization_count
                        ):
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
        except Exception as e:
            context.log.exception(msg=e)
            raise e
        finally:
            connection.close()
            ssh_tunnel.kill()

        item_getter = itemgetter("partitions_def", "partition_key")

        for (partitions_def, partition_key), group in groupby(
            iterable=sorted(run_request_kwargs, key=item_getter), key=item_getter
        ):
            yield RunRequest(
                run_key=f"{partitions_def}_{partition_key}",
                asset_selection=[g["key"] for g in group],
                partition_key=partition_key,
                tags={MAX_RUNTIME_SECONDS_TAG: max_runtime_seconds},
            )

    return _schedule
