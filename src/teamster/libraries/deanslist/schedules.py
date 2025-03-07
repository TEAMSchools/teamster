from itertools import groupby
from operator import itemgetter

from dagster import (
    AssetsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    RunRequest,
    ScheduleEvaluationContext,
    StaticPartitionsDefinition,
    _check,
    schedule,
)

from teamster.core.utils.classes import FiscalYear


def build_deanslist_job_schedule(
    schedule_name: str,
    cron_schedule: str,
    execution_timezone: str,
    asset_selection: list[AssetsDefinition],
    current_fiscal_year: FiscalYear | None = None,
):
    @schedule(
        name=schedule_name,
        cron_schedule=cron_schedule,
        execution_timezone=execution_timezone,
        target=asset_selection,
    )
    def _schedule(context: ScheduleEvaluationContext):
        run_request_kwargs = []

        for asset in asset_selection:
            if isinstance(asset.partitions_def, StaticPartitionsDefinition):
                partitions_def_identifier = (
                    asset.partitions_def.get_serializable_unique_identifier()
                )

                for partition_key in asset.partitions_def.get_partition_keys():
                    run_request_kwargs.append(
                        {
                            "key": asset.key,
                            "partitions_def": partitions_def_identifier,
                            "partition_key": partition_key,
                        }
                    )
            elif isinstance(asset.partitions_def, MultiPartitionsDefinition):
                fy_start_fmt = _check.not_none(
                    value=current_fiscal_year
                ).start.isoformat()

                partitions_def_identifier = (
                    asset.partitions_def.get_serializable_unique_identifier()
                )
                school_partition_keys = (
                    asset.partitions_def.get_partitions_def_for_dimension("school")
                ).get_partition_keys()
                date_partition_keys = (
                    asset.partitions_def.get_partitions_def_for_dimension("date")
                ).get_partition_keys()

                for school in school_partition_keys:
                    for date in date_partition_keys:
                        if date >= fy_start_fmt:
                            run_request_kwargs.append(
                                {
                                    "key": asset.key,
                                    "partitions_def": partitions_def_identifier,
                                    "partition_key": MultiPartitionKey(
                                        {"school": school, "date": date}
                                    ),
                                }
                            )

        item_getter = itemgetter("partitions_def", "partition_key")

        for (partitions_def, partition_key), group in groupby(
            iterable=sorted(run_request_kwargs, key=item_getter), key=item_getter
        ):
            yield RunRequest(
                run_key=f"deanslist_{partitions_def}_{partition_key}",
                asset_selection=[g["key"] for g in group],
                partition_key=partition_key,
            )

    return _schedule
