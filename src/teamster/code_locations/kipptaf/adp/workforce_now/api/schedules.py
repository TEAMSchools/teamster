from dagster import (
    ScheduleDefinition,
    build_schedule_from_partitioned_job,
    define_asset_job,
)

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.adp.workforce_now.api.assets import workers
from teamster.code_locations.kipptaf.adp.workforce_now.api.jobs import (
    adp_wfn_update_workers_job,
)

adp_wfn_worker_fields_update_schedule = ScheduleDefinition(
    job=adp_wfn_update_workers_job,
    cron_schedule="30 5 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

adp_wfn_api_workers_asset_schedule = build_schedule_from_partitioned_job(
    job=define_asset_job(
        name=f"{CODE_LOCATION}_adp_workforce_now_api_workers_asset_job",
        selection=[workers],
    )
)

schedules = [
    adp_wfn_worker_fields_update_schedule,
    adp_wfn_api_workers_asset_schedule,
]
