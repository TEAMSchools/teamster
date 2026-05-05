"""PowerSchool SIS ODBC asset schedule.

Defines a Dagster schedule that yields RunRequests for every asset/partition
in the configured selection (limited to the most recent N monthly partitions
where applicable). Unlike the sensor, the schedule does not consult Oracle —
it runs once per day, the partition window is already constrained, and the
per-asset COUNT(*) probes were a recurring source of DPY-4024 timeouts on
the largest PowerSchool tables.
"""

from itertools import groupby
from operator import itemgetter
from zoneinfo import ZoneInfo

from dagster import (
    AssetsDefinition,
    RunRequest,
    ScheduleDefinition,
    schedule,
)

from teamster.libraries.powerschool.sis.odbc.utils import (
    enumerate_partitions_for_schedule,
)


def build_powerschool_sis_asset_schedule(
    code_location: str,
    execution_timezone: ZoneInfo,
    cron_schedule: str,
    asset_selection: list[AssetsDefinition],
) -> ScheduleDefinition:
    """Build a Dagster schedule that materializes assets without staleness checks.

    Args:
        code_location: District code location identifier.
        execution_timezone: Timezone for schedule evaluation.
        cron_schedule: Cron expression for schedule frequency.
        asset_selection: Assets to materialize.

    Returns:
        A Dagster schedule.
    """

    @schedule(
        name=f"{code_location}__powerschool__sis__asset_job_schedule",
        cron_schedule=cron_schedule,
        execution_timezone=str(execution_timezone),
        target=asset_selection,
    )
    def _schedule():
        results = enumerate_partitions_for_schedule(
            asset_selection=asset_selection,
            limit_monthly_partitions=12,
        )

        kwargs = [
            {
                "key": r.asset_key,
                "partitions_def": r.partitions_def_identifier or "",
                "partition_key": r.partition_key or "",
            }
            for r in results
        ]

        item_getter = itemgetter("partitions_def", "partition_key")

        for (partitions_def, partition_key), group in groupby(
            iterable=sorted(kwargs, key=item_getter), key=item_getter
        ):
            yield RunRequest(
                run_key=f"{partitions_def}_{partition_key}",
                asset_selection=[g["key"] for g in group],
                partition_key=partition_key or None,
            )

    return _schedule
