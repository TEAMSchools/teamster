from dagster import ScheduleDefinition

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.surveys.jobs import survey_email_reminder_job

survey_email_reminder_job_schedule = ScheduleDefinition(
    cron_schedule="0 9 * * 1,3,5",
    execution_timezone=str(LOCAL_TIMEZONE),
    job=survey_email_reminder_job,
)

schedules = [
    survey_email_reminder_job_schedule,
]
