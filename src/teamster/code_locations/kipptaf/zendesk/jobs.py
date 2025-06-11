from dagster import RunConfig, job

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.libraries.google.bigquery.ops import BigQueryOpConfig, bigquery_query_op
from teamster.libraries.zendesk.ops import zendesk_user_sync_op


@job(
    name=f"{CODE_LOCATION}__zendesk__user_sync_job",
    config=RunConfig(
        ops={
            "bigquery_query_op": BigQueryOpConfig(
                dataset_id="kipptaf_extracts", table_id="rpt_zendesk__users"
            )
        }
    ),
    tags={"job_type": "op"},
)
def zendesk_user_sync_op_job():
    users = bigquery_query_op()

    zendesk_user_sync_op(users=users)


jobs = [
    zendesk_user_sync_op_job,
]
