from dagster import ScheduleDefinition

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.tableau.assets import (
    tableau_teacher_gradebook_group_sync,
    workbook_refresh_assets,
)

teacher_gradebook_group_sync_schedule = ScheduleDefinition(
    name=f"{tableau_teacher_gradebook_group_sync.key.to_python_identifier()}_schedule",
    target=tableau_teacher_gradebook_group_sync,
    cron_schedule="0 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

extract_refresh_schedules = [
    ScheduleDefinition(
        name=f"{a.key.to_python_identifier()}_extract_refresh_schedule",
        cron_schedule=a.metadata_by_key[a.key].get("cron_schedule"),
        execution_timezone=str(LOCAL_TIMEZONE),
        target=a,
    )
    for a in workbook_refresh_assets
    if a.metadata_by_key[a.key].get("cron_schedule") is not None
]

schedules = [
    *extract_refresh_schedules,
    teacher_gradebook_group_sync_schedule,
]
