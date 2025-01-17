from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.libraries.fivetran.schedules import (
    build_fivetran_start_resync_schedule,
    build_fivetran_start_sync_schedule,
)

adp_workforce_now_start_resync_schedule = build_fivetran_start_resync_schedule(
    code_location=CODE_LOCATION,
    connector_id="sameness_cunning",
    connector_name="adp_workforce_now",
    cron_schedule="30 0 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

adp_workforce_now_start_sync_schedule = build_fivetran_start_sync_schedule(
    code_location=CODE_LOCATION,
    connector_id="sameness_cunning",
    connector_name="adp_workforce_now",
    cron_schedule="0 4-23 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

coupa_start_sync_schedule = build_fivetran_start_sync_schedule(
    code_location=CODE_LOCATION,
    connector_id="bellows_curliness",
    connector_name="coupa",
    cron_schedule="00 2 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    adp_workforce_now_start_resync_schedule,
    coupa_start_sync_schedule,
]
