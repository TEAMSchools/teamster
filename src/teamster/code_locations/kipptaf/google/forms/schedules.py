from dagster import RunRequest, ScheduleEvaluationContext, schedule

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.google.forms.assets import (
    GOOGLE_FORMS_PARTITIONS_DEF,
)
from teamster.code_locations.kipptaf.google.forms.jobs import google_forms_asset_job


@schedule(
    cron_schedule="0 0 * * *",
    job=google_forms_asset_job,
    execution_timezone=LOCAL_TIMEZONE.name,
)
def google_forms_asset_job_schedule(context: ScheduleEvaluationContext):
    partition_keys = GOOGLE_FORMS_PARTITIONS_DEF.get_partition_keys(
        dynamic_partitions_store=context.instance
    )

    for form_id in partition_keys:
        yield RunRequest(
            run_key=(
                f"{CODE_LOCATION}_google_forms_static_partition_assets_job_{form_id}"
            ),
            partition_key=form_id,
        )


schedules = [
    google_forms_asset_job_schedule,
]
