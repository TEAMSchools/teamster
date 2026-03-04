from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.powerschool.enrollment.assets import (
    submission_records,
)
from teamster.libraries.powerschool.enrollment.schedules import (
    build_pse_submission_records_schedule,
)

pse_submission_records_schedule = build_pse_submission_records_schedule(
    target=submission_records,
    cron_schedule="0 0 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    pse_submission_records_schedule,
]
