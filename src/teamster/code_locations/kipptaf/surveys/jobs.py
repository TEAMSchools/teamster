from pathlib import Path

from dagster import RunConfig, job

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.libraries.email.ops import (
    SendPersonalizedEmailOpConfig,
    send_personalized_email_op,
)
from teamster.libraries.google.bigquery.ops import BigQueryOpConfig, bigquery_query_op

TEXT_TEMPLATE = """Welcome to the Fall 2026 survey window! Your feedback is critical to shaping our next strategic plan.

Your surveys still to complete:
{% for item in items %}
- {{ item.survey }}: {{ item.link }}
{% endfor %}
These links are just for you, so please don't forward this email. You can also find your links and completion status at Survey HQ:
https://tableau.kipp.org/t/KIPPNJ/views/PersonalizedSurveyLinks/SurveyHQ?%3Aembed=y

Survey Window: October 19 - November 6, 2026

Google Chrome is required, and you must be signed into your KIPP Google account to open the surveys.

If you run into any issues, please share details via a ticket with surveys@kippteamandfamily.org.

All our best,
The Survey Team
"""


@job(
    name=f"{CODE_LOCATION}__surveys__email_reminder",
    config=RunConfig(
        ops={
            "bigquery_query_op": BigQueryOpConfig(
                dataset_id="kipptaf_extracts", table_id="rpt_extracts__survey_reminder"
            ),
            "send_personalized_email_op": SendPersonalizedEmailOpConfig(
                subject="Survey Reminder: You have surveys to complete",
                text_template=TEXT_TEMPLATE,
                html_template_path=str(Path(__file__).parent / "template.html"),
            ),
        }
    ),
    tags={"job_type": "op", "dagster/max_runtime": "7200"},
)
def survey_email_reminder_job():
    recipients = bigquery_query_op()

    send_personalized_email_op(recipients=recipients)
