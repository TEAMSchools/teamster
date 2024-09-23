from dagster import ScheduleDefinition, define_asset_job

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf._google.directory.assets import (
    google_directory_nonpartitioned_assets,
)
from teamster.code_locations.kipptaf._google.directory.jobs import (
    google_directory_role_assignments_sync_job,
    google_directory_user_sync_job,
)

google_directory_nonpartitioned_asset_schedule = ScheduleDefinition(
    job=define_asset_job(
        name=f"{CODE_LOCATION}__google__directory__nonpartitioned_asset_job",
        selection=[a.key for a in google_directory_nonpartitioned_assets],
    ),
    cron_schedule="0 1 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

google_directory_role_assignments_sync_schedule = ScheduleDefinition(
    job=google_directory_role_assignments_sync_job,
    cron_schedule="0 3 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

google_directory_user_sync_schedule = ScheduleDefinition(
    job=google_directory_user_sync_job,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

schedules = [
    google_directory_nonpartitioned_asset_schedule,
    google_directory_role_assignments_sync_schedule,
    google_directory_user_sync_schedule,
]
