from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.amplify.dibels.assets import (
    data_farming,
    progress_export,
)
from teamster.libraries.amplify.dibels.schedules import build_amplify_dibels_schedule

amplify_dibels_data_farming_asset_job_schedule = build_amplify_dibels_schedule(
    asset=data_farming,
    cron_schedule="0 4 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

amplify_dibels_progress_export_asset_job_schedule = build_amplify_dibels_schedule(
    asset=progress_export,
    cron_schedule="0 4 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

schedules = [
    amplify_dibels_data_farming_asset_job_schedule,
]
