from dagster import RunRequest, ScheduleEvaluationContext, schedule

from teamster.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.kipptaf.google.forms.assets import FORM_IDS
from teamster.kipptaf.google.forms.jobs import google_forms_asset_job


@schedule(
    cron_schedule="0 0 * * *",
    job=google_forms_asset_job,
    execution_timezone=LOCAL_TIMEZONE.name,
)
def google_forms_asset_job_schedule(context: ScheduleEvaluationContext):
    for form_id in FORM_IDS:
        yield RunRequest(
            run_key=(
                f"{CODE_LOCATION}_google_forms_static_partition_assets_job_{form_id}"
            ),
            partition_key=form_id,
        )


schedules = [
    google_forms_asset_job_schedule,
]
