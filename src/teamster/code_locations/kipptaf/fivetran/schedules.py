from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.libraries.fivetran.schedules import build_fivetran_start_sync_schedule

coupa_start_sync_schedule = build_fivetran_start_sync_schedule(
    code_location=CODE_LOCATION,
    connector_id="bellows_curliness",
    connector_name="coupa",
    cron_schedule="00 2 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    coupa_start_sync_schedule,
]
