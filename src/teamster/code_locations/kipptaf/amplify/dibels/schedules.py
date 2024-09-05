from dagster import RunRequest, ScheduleEvaluationContext, define_asset_job, schedule

from teamster.code_locations.kipptaf import CURRENT_FISCAL_YEAR, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.amplify.dibels.assets import data_farming

amplify_dibels_asset_job = define_asset_job(
    name=f"{data_farming.key.to_python_identifier()}_asset_job",
    selection=[data_farming],
    partitions_def=data_farming.partitions_def,
)


@schedule(
    name=f"{amplify_dibels_asset_job.name}_schedule",
    cron_schedule="0 4 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=amplify_dibels_asset_job,
)
def amplify_dibels_asset_job_schedule(context: ScheduleEvaluationContext):
    yield RunRequest(partition_key=CURRENT_FISCAL_YEAR.start.to_date_string())


schedules = [
    amplify_dibels_asset_job_schedule,
]
