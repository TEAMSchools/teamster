"""from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.libraries.fivetran.schedules import build_fivetran_start_sync_schedule

illuminate_start_sync_schedule = build_fivetran_start_sync_schedule(
    code_location=CODE_LOCATION,
    connector_id="jinx_credulous",
    connector_name="illuminate",
    cron_schedule="5 * * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

illuminate_xmin_start_sync_schedule = build_fivetran_start_sync_schedule(
    code_location=CODE_LOCATION,
    connector_id="genuine_describing",
    connector_name="illuminate_xmin",
    cron_schedule="0 * * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    illuminate_start_sync_schedule,
    illuminate_xmin_start_sync_schedule,
]
"""
