import time
from datetime import datetime
from itertools import groupby
from operator import itemgetter
from typing import Mapping
from zoneinfo import ZoneInfo

from dagster import (
    MAX_RUNTIME_SECONDS_TAG,
    AssetKey,
    AssetsDefinition,
    DagsterEventType,
    EventRecordsFilter,
    MetadataValue,
    MonthlyPartitionsDefinition,
    RunRequest,
    ScheduleEvaluationContext,
    _check,
    schedule,
)
from dateutil.relativedelta import relativedelta

from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.powerschool.sis.resources import PowerSchoolODBCResource
from teamster.libraries.powerschool.sis.utils import get_query_text, open_ssh_tunnel
from teamster.libraries.ssh.resources import SSHResource


def get_datetime_from_metadata(
    metadata: Mapping[str, MetadataValue], execution_timezone: ZoneInfo
):
    timestamp = _check.inst(
        obj=metadata["latest_materialization_timestamp"].value, ttype=float
    )

    return (
        datetime.fromtimestamp(timestamp=timestamp, tz=execution_timezone)
        .replace(tzinfo=None)
        .isoformat(timespec="microseconds")
    )


def get_count(
    db_powerschool: PowerSchoolODBCResource,
    table: str,
    column: str | None = None,
    start_value: str | None = None,
    end_value: str | None = None,
) -> int:
    [(count,)] = _check.inst(
        db_powerschool.execute_query(
            query=get_query_text(
                table=table, column=column, start_value=start_value, end_value=end_value
            ),
            prefetch_rows=2,
            array_size=1,
        ),
        list,
    )

    return count


def foo_nonpartitioned(
    asset_key: AssetKey,
    asset_key_identifier: str,
    table_name: str,
    partition_column: str,
    context: ScheduleEvaluationContext,
    execution_timezone: ZoneInfo,
    db_powerschool: PowerSchoolODBCResource,
    materialization_metadata: Mapping[str, MetadataValue],
) -> dict | None:
    # request run if table modified count > 0
    if partition_column is not None:
        modified_count = get_count(
            db_powerschool=db_powerschool,
            table=table_name,
            column=partition_column,
            start_value=get_datetime_from_metadata(
                metadata=materialization_metadata, execution_timezone=execution_timezone
            ),
        )

        if modified_count > 0:
            context.log.info(
                msg=f"{asset_key_identifier}\nmodified count: {modified_count}"
            )
            return {"asset_key": asset_key, "partitions_def": "", "partition_key": ""}

    # request run if table count doesn't match latest materialization
    # catches deleted records
    table_count = get_count(db_powerschool=db_powerschool, table=table_name)
    materialization_count = materialization_metadata["records"].value

    if table_count != materialization_count:
        context.log.info(
            msg=(
                f"{asset_key_identifier}\n"
                f"PS count ({table_count}) != DB count ({materialization_count})"
            )
        )
        return {"asset_key": asset_key, "partitions_def": "", "partition_key": ""}
    else:
        return None


def foo_partitioned(
    asset_key: AssetKey,
    asset_key_identifier: str,
    table_name: str,
    partition_column: str,
    context: ScheduleEvaluationContext,
    execution_timezone: ZoneInfo,
    db_powerschool: PowerSchoolODBCResource,
    partition_key: str,
    partitions_def_identifier: str,
    first_partition_key: str,
    last_partition_key: str,
    date_add_kwargs: dict,
) -> dict | None:
    event_record = context.instance.get_event_records(
        event_records_filter=EventRecordsFilter(
            event_type=DagsterEventType.ASSET_MATERIALIZATION,
            asset_key=asset_key,
            asset_partitions=[partition_key],
        ),
        limit=1,
    )

    # request run if partition never materialized
    if not event_record:
        context.log.info(msg=f"{asset_key_identifier} never materialized")
        return {
            "asset_key": asset_key,
            "partitions_def": partitions_def_identifier,
            "partition_key": partition_key,
        }
    else:
        materialization_metadata = _check.not_none(
            value=event_record[0].asset_materialization
        ).metadata

    # skip first partition
    if partition_key == first_partition_key:
        return None
    # request run if last partition modified count > 0
    elif partition_key == last_partition_key:
        modified_count = get_count(
            db_powerschool=db_powerschool,
            table=table_name,
            column=partition_column,
            start_value=get_datetime_from_metadata(
                metadata=materialization_metadata, execution_timezone=execution_timezone
            ),
        )

        if modified_count > 0:
            context.log.info(
                msg=(
                    f"{asset_key_identifier}\n{partition_key}\n"
                    f"modified count: {modified_count}"
                )
            )
            return {
                "asset_key": asset_key,
                "partitions_def": partitions_def_identifier,
                "partition_key": partition_key,
            }

    # request run if partition count != latest materialization
    # catches deleted records
    partition_start = datetime.fromisoformat(partition_key)

    partition_end = (
        partition_start + relativedelta(**date_add_kwargs) - relativedelta(days=1)
    ).replace(hour=23, minute=59, second=59, microsecond=999999)

    partition_count = get_count(
        db_powerschool=db_powerschool,
        table=table_name,
        column=partition_column,
        start_value=partition_start.replace(tzinfo=None).isoformat(
            timespec="microseconds"
        ),
        end_value=partition_end.replace(tzinfo=None).isoformat(timespec="microseconds"),
    )

    materialization_count = materialization_metadata["records"].value

    if partition_count > 0 and partition_count != materialization_count:
        context.log.info(
            msg=(
                f"{asset_key_identifier}\n{partition_key}\n"
                f"PS count ({partition_count}) != DB count ({materialization_count})"
            )
        )
        return {
            "asset_key": asset_key,
            "partitions_def": partitions_def_identifier,
            "partition_key": partition_key,
        }
    else:
        return None


def build_powerschool_sis_asset_schedule(
    code_location: str,
    execution_timezone: ZoneInfo,
    cron_schedule: str,
    asset_selection: list[AssetsDefinition],
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
        run_request_kwargs_list: list[dict | None] = []

        latest_materialization_events = (
            context.instance.get_latest_materialization_events(asset_keys)
        )

        context.log.info(msg=f"Opening SSH tunnel to {ssh_powerschool.remote_host}")
        ssh_tunnel = open_ssh_tunnel(ssh_powerschool)

        time.sleep(1.0)

        try:
            for asset in asset_selection:
                asset_metadata = asset.metadata_by_key[asset.key]

                # non-partitioned assets
                if asset.partitions_def is None:
                    latest_materialization_event = latest_materialization_events.get(
                        asset.key
                    )
                    # request run if asset never materialized
                    if latest_materialization_event is None:
                        context.log.info(
                            msg=f"{asset.key.to_python_identifier()} never materialized"
                        )
                        run_request_kwargs = {
                            "asset_key": asset.key,
                            "partitions_def": "",
                            "partition_key": "",
                        }
                    else:
                        run_request_kwargs = foo_nonpartitioned(
                            asset_key=asset.key,
                            asset_key_identifier=asset.key.to_python_identifier(),
                            table_name=asset_metadata["table_name"],
                            partition_column=asset_metadata["partition_column"],
                            context=context,
                            execution_timezone=execution_timezone,
                            db_powerschool=db_powerschool,
                            materialization_metadata=_check.not_none(
                                latest_materialization_event.asset_materialization
                            ).metadata,
                        )

                    run_request_kwargs_list.append(run_request_kwargs)
                # partitioned assets
                else:
                    partitions_def = asset.partitions_def

                    partition_keys = partitions_def.get_partition_keys()

                    if isinstance(partitions_def, FiscalYearPartitionsDefinition):
                        date_add_kwargs = {"years": 1}
                    elif isinstance(partitions_def, MonthlyPartitionsDefinition):
                        date_add_kwargs = {"months": 1}
                        partition_keys = partition_keys[-12:]  # limit to 12 months
                    else:
                        date_add_kwargs = {}

                    for partition_key in partition_keys:
                        run_request_kwargs = foo_partitioned(
                            asset_key=asset.key,
                            asset_key_identifier=asset.key.to_python_identifier(),
                            table_name=asset_metadata["table_name"],
                            partition_column=asset_metadata["partition_column"],
                            context=context,
                            execution_timezone=execution_timezone,
                            db_powerschool=db_powerschool,
                            partition_key=partition_key,
                            partitions_def_identifier=(
                                partitions_def.get_serializable_unique_identifier()
                            ),
                            first_partition_key=_check.not_none(
                                value=partitions_def.get_first_partition_key()
                            ),
                            last_partition_key=_check.not_none(
                                value=partitions_def.get_last_partition_key()
                            ),
                            date_add_kwargs=date_add_kwargs,
                        )

                        run_request_kwargs_list.append(run_request_kwargs)
        except Exception as e:
            context.log.exception(msg=e)
            raise e
        finally:
            ssh_tunnel.kill()

        item_getter = itemgetter("partitions_def", "partition_key")
        run_request_kwargs_filtered = [
            k for k in run_request_kwargs_list if k is not None
        ]

        for (partitions_def, partition_key), group in groupby(
            iterable=sorted(run_request_kwargs_filtered, key=item_getter),
            key=item_getter,
        ):
            yield RunRequest(
                run_key=f"{partitions_def}_{partition_key}",
                asset_selection=[g["asset_key"] for g in group],
                partition_key=partition_key,
                tags={MAX_RUNTIME_SECONDS_TAG: (60 * 10)},
            )

    return _schedule
