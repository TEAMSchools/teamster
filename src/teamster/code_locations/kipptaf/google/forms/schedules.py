from datetime import datetime, timedelta, timezone
from typing import Generator

from dagster import (
    RunRequest,
    ScheduleEvaluationContext,
    define_asset_job,
    in_process_executor,
    schedule,
)

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.google.forms.assets import (
    GOOGLE_FORMS_PARTITIONS_DEF,
    form,
)
from teamster.libraries.google.drive.resources import GoogleDriveResource

# In process: a step pod per form doubles the midnight pod burst that GKE
# preempts on new nodes (#6225).
google_forms_asset_job = define_asset_job(
    # trunk-ignore(pyright/reportFunctionMemberAccess)
    name=f"{form.key.to_python_identifier()}_asset_job",
    # trunk-ignore(pyright/reportArgumentType)
    selection=[form],
    executor_def=in_process_executor,
)


@schedule(
    # trunk-ignore(pyright/reportFunctionMemberAccess)
    name=f"{form.key.to_python_identifier()}_schedule",
    target=google_forms_asset_job,
    cron_schedule="0 0 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)
def google_forms_asset_job_schedule(
    context: ScheduleEvaluationContext, google_drive: GoogleDriveResource
) -> Generator:
    partition_keys = GOOGLE_FORMS_PARTITIONS_DEF.get_partition_keys(
        dynamic_partitions_store=context.instance
    )

    # A new response does not change a form's Drive modifiedTime; only an edit
    # to the form does. Look up partition keys, not the shared folder: some
    # forms with responses live in personal My Drives.
    # shortcut: a failed form run is not retried the next night unless the form
    # is edited again; materialize it by hand.
    # the public property raises when no tick time is set (manual evaluation)
    tick = context._scheduled_execution_time or datetime.now(timezone.utc)
    cutoff = (tick - timedelta(hours=25)).timestamp()
    modified_times = google_drive.get_modified_times(
        file_ids=list(partition_keys), logger=context.log
    )

    for form_id in partition_keys:
        # a failed lookup is omitted from modified_times: pull the form anyway
        if modified_times.get(form_id, cutoff) >= cutoff:
            yield RunRequest(
                run_key=f"{context._schedule_name}_{form_id}", partition_key=form_id
            )


schedules = [
    google_forms_asset_job_schedule,
]
