from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.libraries.fivetran.schedules import (
    build_fivetran_start_resync_schedule,
    build_fivetran_start_sync_schedule,
)

adp_workforce_now_start_resync_schedule = build_fivetran_start_resync_schedule(
    code_location=CODE_LOCATION,
    connector_id="sameness_cunning",
    connector_name="adp_workforce_now",
    cron_schedule="0 20 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

adp_workforce_now_start_sync_schedule = build_fivetran_start_sync_schedule(
    code_location=CODE_LOCATION,
    connector_id="sameness_cunning",
    connector_name="adp_workforce_now",
    cron_schedule="0 0-19 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

illuminate_start_sync_schedule = build_fivetran_start_sync_schedule(
    code_location=CODE_LOCATION,
    connector_id="jinx_credulous",
    connector_name="illuminate",
    cron_schedule="5 * * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

illuminate_xmin_start_sync_schedule = build_fivetran_start_sync_schedule(
    code_location=CODE_LOCATION,
    connector_id="genuine_describing",
    connector_name="illuminate_xmin",
    cron_schedule="0 * * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

coupa_start_sync_schedule = build_fivetran_start_sync_schedule(
    code_location=CODE_LOCATION,
    connector_id="bellows_curliness",
    connector_name="coupa",
    cron_schedule="0 * * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

facebook_pages_start_sync_schedule = build_fivetran_start_sync_schedule(
    code_location=CODE_LOCATION,
    connector_id="regency_carrying",
    connector_name="facebook_pages",
    cron_schedule="0 * * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

instagram_business_start_sync_schedule = build_fivetran_start_sync_schedule(
    code_location=CODE_LOCATION,
    connector_id="muskiness_cumulative",
    connector_name="instagram_business",
    cron_schedule="0 * * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

schedules = [
    adp_workforce_now_start_resync_schedule,
    adp_workforce_now_start_sync_schedule,
    coupa_start_sync_schedule,
    facebook_pages_start_sync_schedule,
    illuminate_start_sync_schedule,
    illuminate_xmin_start_sync_schedule,
    instagram_business_start_sync_schedule,
]
