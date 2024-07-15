from typing import Generator

from dagster import RunRequest, ScheduleEvaluationContext, define_asset_job, schedule

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.google.forms.assets import (
    GOOGLE_FORMS_PARTITIONS_DEF,
    form,
    responses,
)

job = define_asset_job(
    name=f"{CODE_LOCATION}_google_forms_asset_job", selection=[form, responses]
)


@schedule(
    name=f"{job.name}_schedule",
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=job,
)
def google_forms_asset_job_schedule(context: ScheduleEvaluationContext) -> Generator:
    partition_keys = GOOGLE_FORMS_PARTITIONS_DEF.get_partition_keys(
        dynamic_partitions_store=context.instance
    )

    for form_id in partition_keys:
        yield RunRequest(
            run_key=f"{context._schedule_name}_{form_id}", partition_key=form_id
        )


schedules = [
    google_forms_asset_job_schedule,
]
