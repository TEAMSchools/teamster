from dagster import ScheduleDefinition, build_schedule_from_partitioned_job

from teamster.core.utils.variables import LOCAL_TIME_ZONE

from .jobs import ps_db_asset_job, ps_db_partitioned_asset_job

ps_db_partitioned_asset_schedule = build_schedule_from_partitioned_job(
    job=ps_db_partitioned_asset_job,
)

ps_db_asset_schedule = ScheduleDefinition(
    job=ps_db_asset_job,
    cron_schedule="0 0 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

__all__ = [ps_db_partitioned_asset_schedule, ps_db_asset_schedule]
