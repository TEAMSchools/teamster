from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.libraries.airbyte.schedules import build_airbyte_start_sync_schedule

zendesk_start_sync_schedule = build_airbyte_start_sync_schedule(
    code_location=CODE_LOCATION,
    connection_id="ee23720c-c82f-45be-ab40-f72dcf8ac3cd",
    connection_name="zendesk",
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

kippadb_start_sync_schedule = build_airbyte_start_sync_schedule(
    code_location=CODE_LOCATION,
    connection_id="e4856fb7-1f97-4bcd-bc4e-e616c5ae4e52",
    connection_name="kippadb",
    cron_schedule=["0 0 * * *", "15 16 * * *"],
    execution_timezone=LOCAL_TIMEZONE.name,
)

schedules = [
    kippadb_start_sync_schedule,
    zendesk_start_sync_schedule,
]
