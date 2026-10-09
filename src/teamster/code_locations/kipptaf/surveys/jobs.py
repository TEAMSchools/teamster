from pathlib import Path

from dagster import RunConfig, job

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.libraries.email.ops import (
    SendPersonalizedEmailOpConfig,
    send_personalized_email_op,
)
from teamster.libraries.google.bigquery.ops import BigQueryOpConfig, bigquery_query_op


@job(
    name=f"{CODE_LOCATION}__surveys__email_reminder",
    config=RunConfig(
        ops={
            "bigquery_query_op": BigQueryOpConfig(
                dataset_id="kipptaf_extracts", table_id="rpt_extracts__survey_reminder"
            ),
            "send_personalized_email_op": SendPersonalizedEmailOpConfig(
                subject="Survey Reminder: You have surveys to complete",
                html_template_path=str(Path(__file__).parent / "template.html"),
            ),
        }
    ),
    # a retry would re-email everyone who was already sent to before the failure
    tags={
        "job_type": "op",
        "dagster/max_runtime": "14400",
        "dagster/max_retries": "0",
    },
)
def survey_email_reminder_job():
    recipients = bigquery_query_op()

    send_personalized_email_op(recipients=recipients)
