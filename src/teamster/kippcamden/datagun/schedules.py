from dagster import ScheduleDefinition

from teamster.core.utils.variables import LOCAL_TIME_ZONE
from teamster.kippcamden.datagun import jobs

powerschool_extract_assets_schedule = ScheduleDefinition(
    job=jobs.powerschool_extract_assets_job,
    cron_schedule="15 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

cpn_extract_assets_schedule = ScheduleDefinition(
    job=jobs.cpn_extract_assets_job,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIME_ZONE.name,
)

__all__ = [cpn_extract_assets_schedule, powerschool_extract_assets_schedule]
