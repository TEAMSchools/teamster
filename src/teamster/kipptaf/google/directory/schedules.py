from dagster import ScheduleDefinition

from ... import LOCAL_TIMEZONE
from .jobs import (
    google_directory_nonpartitioned_asset_job,
    google_directory_role_assignments_sync_job,
    google_directory_user_sync_job,
)

google_directory_nonpartitioned_asset_schedule = ScheduleDefinition(
    job=google_directory_nonpartitioned_asset_job,
    cron_schedule="0 1 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

google_directory_role_assignments_sync_schedule = ScheduleDefinition(
    job=google_directory_role_assignments_sync_job,
    cron_schedule="30 2 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

google_directory_user_sync_schedule = ScheduleDefinition(
    job=google_directory_user_sync_job,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

_all = [
    google_directory_nonpartitioned_asset_schedule,
    google_directory_role_assignments_sync_schedule,
    google_directory_user_sync_schedule,
]
