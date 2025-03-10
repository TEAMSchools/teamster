from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.libraries.airbyte.schedules import build_airbyte_start_sync_schedule

kippadb_start_sync_schedule = build_airbyte_start_sync_schedule(
    code_location=CODE_LOCATION,
    connection_id="e4856fb7-1f97-4bcd-bc4e-e616c5ae4e52",
    connection_name="kippadb",
    cron_schedule=["0 3 * * *", "15 16 * * *"],
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    kippadb_start_sync_schedule,
]
