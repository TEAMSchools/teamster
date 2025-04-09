from dagster import EnvVar, _check, build_op_context

from teamster.core.resources import BIGQUERY_RESOURCE
from teamster.libraries.email.ops import SendEmailOpConfig, send_email_op
from teamster.libraries.email.resources import EmailResource
from teamster.libraries.google.bigquery.ops import BigQueryOpConfig, bigquery_query_op


def test_send_email_job():
    # from teamster.code_locations.kipptaf.resources import OUTLOOK_RESOURCE

    TEXT_BODY = """
    Please take a few minutes to complete your pending surveys on Survey HQ.

    Thank you,
    Survey Team
    """

    context = build_op_context()

    recipients = bigquery_query_op(
        context=context,
        db_bigquery=BIGQUERY_RESOURCE,
        config=BigQueryOpConfig(
            dataset_id="z_dev_kipptaf_extracts",
            table_id="rpt_extracts__survey_reminder",
        ),
    )

    data = send_email_op(
        context=context,
        # email=OUTLOOK_RESOURCE,
        email=EmailResource(
            host=EnvVar("MAILTRAP_HOST"),
            port=int(_check.not_none(value=EnvVar("MAILTRAP_PORT").get_value())),
            user=EnvVar("MAILTRAP_USER"),
            password=EnvVar("MAILTRAP_PASSWORD"),
            chunk_size=450,
            test=True,
        ),
        config=SendEmailOpConfig(
            subject="Survey Reminder: You have pending surveys in Survey HQ!",
            text_body=TEXT_BODY,
            template_path="src/teamster/code_locations/kipptaf/surveys/template.html",
        ),
        recipients=recipients,
    )

    context.log.info(data)
