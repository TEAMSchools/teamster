from dagster import ScheduleDefinition

from teamster.core.utils.variables import LOCAL_TIME_ZONE
from teamster.kippnewark.datagun.jobs import (
    nps_extract_assets_job,
    powerschool_extract_assets_job,
)

powerschool_extract_assets_schedule = ScheduleDefinition(
    job=powerschool_extract_assets_job,
    cron_schedule="15 2 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)

nps_extract_assets_schedule = ScheduleDefinition(
    job=nps_extract_assets_job,
    cron_schedule="0 0 * * *",
    execution_timezone=str(LOCAL_TIME_ZONE),
)
