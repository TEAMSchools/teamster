from dagster import ScheduleDefinition, define_asset_job, in_process_executor

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.tableau.assets import (
    tableau_teacher_gradebook_group_sync,
    workbook_refresh_assets,
)

teacher_gradebook_group_sync_schedule = ScheduleDefinition(
    name=f"{tableau_teacher_gradebook_group_sync.key.to_python_identifier()}_schedule",
    target=define_asset_job(
        name=f"{tableau_teacher_gradebook_group_sync.key.to_python_identifier()}_asset_job",
        selection=[tableau_teacher_gradebook_group_sync],
        executor_def=in_process_executor,
    ),
    cron_schedule="20 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

# In process: these one-asset refreshes fire at the top of the hour, and a step
# pod each adds to the bursts that GKE preempts on new nodes (#6225).
extract_refresh_schedules = [
    ScheduleDefinition(
        name=f"{a.key.to_python_identifier()}_extract_refresh_schedule",
        cron_schedule=a.metadata_by_key[a.key].get("cron_schedule"),
        execution_timezone=str(LOCAL_TIMEZONE),
        target=define_asset_job(
            name=f"{a.key.to_python_identifier()}_extract_refresh_asset_job",
            selection=[a],
            executor_def=in_process_executor,
        ),
    )
    for a in workbook_refresh_assets
    if a.metadata_by_key[a.key].get("cron_schedule") is not None
]

schedules = [
    *extract_refresh_schedules,
    teacher_gradebook_group_sync_schedule,
]
