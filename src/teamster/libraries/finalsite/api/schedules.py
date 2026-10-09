from collections.abc import Sequence

from dagster import (
    MAX_RUNTIME_SECONDS_TAG,
    AssetsDefinition,
    RunRequest,
    ScheduleDefinition,
    ScheduleEvaluationContext,
    schedule,
)


def build_finalsite_contacts_schedule(
    code_location: str,
    execution_timezone: str,
    asset_selection: list[AssetsDefinition],
    cron_schedule: Sequence[str] = ("15 0 * * *", "0 12 * * *"),
    max_runtime_seconds: int = 900,
) -> ScheduleDefinition:
    """Build the twice-daily incremental contacts schedule for one district.

    Both ticks target the SAME daily partition: 00:15 lands before the 01:00
    Google Directory account sync and the 01:25 DeansList ship, and 12:00 feeds
    the midday Focus import cycle. Neither is top-of-hour, where GKE Autopilot
    fan-out adds 3-9 minutes of step-pod scheduling wait.

    The name is deliberately unchanged from the pre-incremental schedule --
    renaming mints a NEW Dagster+ schedule object and abandons this one's status
    and tick history -- so "daily" now means twice a day.
    """

    @schedule(
        name=f"{code_location}__finalsite__contacts__daily_asset_job_schedule",
        cron_schedule=list(cron_schedule),
        execution_timezone=execution_timezone,
        target=asset_selection,
    )
    def _schedule(context: ScheduleEvaluationContext):
        # run_key stays None: both daily ticks share a partition key, and a
        # run_key equal to it would dedupe the second run away.
        yield RunRequest(
            partition_key=context.scheduled_execution_time.date().isoformat(),
            tags={MAX_RUNTIME_SECONDS_TAG: str(max_runtime_seconds)},
        )

    return _schedule
