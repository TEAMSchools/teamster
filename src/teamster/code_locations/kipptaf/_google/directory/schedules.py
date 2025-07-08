from dagster import ScheduleDefinition, define_asset_job

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf._google.directory.assets import (
    google_directory_nonpartitioned_assets,
    google_directory_role_assignments_create,
    google_directory_user_create,
    google_directory_user_update,
)

asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__google__directory__nonpartitioned_asset_job",
    selection=[a.key for a in google_directory_nonpartitioned_assets],
)

google_directory_nonpartitioned_asset_schedule = ScheduleDefinition(
    name=f"{asset_job.name}_schedule",
    target=asset_job,
    cron_schedule="30 1 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

google_directory_role_assignments_create_schedule = ScheduleDefinition(
    name=(
        google_directory_role_assignments_create.key.to_python_identifier()
        + "_schedule"
    ),
    target=google_directory_role_assignments_create,
    cron_schedule="0 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

google_directory_user_sync_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__google__directory__user_sync_schedule",
    target=[google_directory_user_create, google_directory_user_update],
    cron_schedule="0 1 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    google_directory_nonpartitioned_asset_schedule,
    google_directory_role_assignments_create_schedule,
    google_directory_user_sync_schedule,
]
