from teamster.code_locations.kippmiami import CODE_LOCATION
from teamster.code_locations.kippmiami.dlt.focus.assets import (
    sql_database_credentials,
    tables,
)
from teamster.code_locations.kippmiami.dlt.focus.schedules import (
    focus_dlt_daily_asset_job_schedule,
)
from teamster.libraries.dlt.focus.sensors import build_focus_dlt_intraday_sensor

sensors = [
    build_focus_dlt_intraday_sensor(
        code_location=CODE_LOCATION,
        tables=tables,
        sql_database_credentials=sql_database_credentials,
        # References the real schedule object rather than retyping its name --
        # a drift between the two would make the in-flight guard (which reads
        # the `dagster/schedule_name` run tag) stop matching and double-launch.
        nightly_schedule_name=focus_dlt_daily_asset_job_schedule.name,
    )
]
