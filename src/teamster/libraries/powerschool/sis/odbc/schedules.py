"""PowerSchool SIS ODBC asset schedule.

Defines a Dagster schedule that evaluates PowerSchool assets for staleness
and yields RunRequests for stale assets grouped by partition definition
and partition key.
"""

from itertools import groupby
from operator import itemgetter
from zoneinfo import ZoneInfo

from dagster import (
    AssetsDefinition,
    RunRequest,
    ScheduleDefinition,
    ScheduleEvaluationContext,
    schedule,
)

from teamster.libraries.powerschool.sis.odbc.resources import PowerSchoolODBCResource
from teamster.libraries.powerschool.sis.odbc.utils import (
    evaluate_asset_staleness,
    with_powerschool_retry,
)
from teamster.libraries.ssh.resources import SSHResource


def build_powerschool_sis_asset_schedule(
    code_location: str,
    execution_timezone: ZoneInfo,
    cron_schedule: str,
    asset_selection: list[AssetsDefinition],
) -> ScheduleDefinition:
    """Build a Dagster schedule that detects and rematerializes stale assets.

    Args:
        code_location: District code location identifier.
        execution_timezone: Timezone for schedule evaluation.
        cron_schedule: Cron expression for schedule frequency.
        asset_selection: Assets to monitor for staleness.

    Returns:
        A Dagster schedule function.
    """

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
        results = with_powerschool_retry(
            ssh_resource=ssh_powerschool,
            db_resource=db_powerschool,
            log=context.log,
            work_fn=lambda conn: evaluate_asset_staleness(
                asset_selection=asset_selection,
                execution_timezone=execution_timezone,
                instance=context.instance,
                connection=conn,
                db_powerschool=db_powerschool,
                log=context.log,
                limit_monthly_partitions=12,
            ),
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
