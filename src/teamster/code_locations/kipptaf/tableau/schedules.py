from dagster import ScheduleDefinition

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.tableau.assets import workbook_refresh_assets

schedules = [
    ScheduleDefinition(
        name=f"{a.key.to_python_identifier()}_extract_refresh_schedule",
        cron_schedule=a.metadata_by_key[a.key].get("cron_schedule"),
        execution_timezone=str(LOCAL_TIMEZONE),
        target=a,
    )
    for a in workbook_refresh_assets
    if a.metadata_by_key[a.key].get("cron_schedule") is not None
]
