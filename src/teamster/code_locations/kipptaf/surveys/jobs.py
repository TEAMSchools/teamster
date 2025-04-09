from pathlib import Path

from dagster import RunConfig, job

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.libraries.email.ops import SendEmailOpConfig, send_email_op
from teamster.libraries.google.bigquery.ops import BigQueryOpConfig, bigquery_query_op

TEXT_BODY = """Please take a few minutes to complete your pending surveys on Survey HQ.

Thank you,
Survey Team
"""


@job(
    name=f"{CODE_LOCATION}__surveys__email_reminder",
    config=RunConfig(
        ops={
            "bigquery_query_op": BigQueryOpConfig(
                dataset_id="kipptaf_extracts", table_id="rpt_extracts__survey_reminder"
            ),
            "send_email_op": SendEmailOpConfig(
                subject="Survey Reminder: You have pending surveys in Survey HQ!",
                text_body=TEXT_BODY,
                template_path=Path(__file__).parent / "template.html",
            ),
        }
    ),
    tags={"job_type": "op"},
)
def survey_email_reminder_job():
    recipients = bigquery_query_op()

    if recipients:
        send_email_op(recipients=recipients)
