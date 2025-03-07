from itertools import groupby
from operator import itemgetter
from typing import Generator

from dagster import (
    AssetsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    RunRequest,
    ScheduleEvaluationContext,
    StaticPartitionsDefinition,
    schedule,
)

from teamster.core.utils.classes import FiscalYear


def build_deanslist_job_schedule(
    cron_schedule: str,
    execution_timezone: str,
    asset_selection: list[AssetsDefinition],
    current_fiscal_year: FiscalYear,
    code_location: str | None = None,
    schedule_name: str | None = None,
):
    if schedule_name is None:
        schedule_name = f"{code_location}__deanslist__partitioned_asset_job_schedule"

    @schedule(
        name=schedule_name,
        cron_schedule=cron_schedule,
        execution_timezone=execution_timezone,
        target=asset_selection,
    )
    def _schedule(context: ScheduleEvaluationContext) -> Generator:
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
                        if date >= current_fiscal_year.start.isoformat():
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
