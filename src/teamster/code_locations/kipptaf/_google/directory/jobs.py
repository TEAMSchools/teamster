from dagster import RunConfig, job

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.libraries.google.bigquery.ops import BigQueryOpConfig, bigquery_query_op
from teamster.libraries.google.directory.ops import (
    google_directory_member_create_op,
    google_directory_role_assignment_create_op,
    google_directory_user_create_op,
    google_directory_user_update_op,
)


@job(
    name=f"{CODE_LOCATION}__google__directory__user_sync_job",
    config=RunConfig(
        ops={
            "bigquery_query_op": BigQueryOpConfig(
                dataset_id="kipptaf_extracts",
                table_id="rpt_google_directory__users_import",
            )
        }
    ),
    tags={"job_type": "op"},
)
def google_directory_user_sync_job():
    users = bigquery_query_op()

    members = google_directory_user_create_op(users=users)
    google_directory_user_update_op(users=users)

    google_directory_member_create_op(members=members)


@job(
    name=f"{CODE_LOCATION}__google__directory__role_assignments_sync_job",
    config=RunConfig(
        ops={
            "bigquery_query_op": BigQueryOpConfig(
                dataset_id="kipptaf_extracts",
                table_id="rpt_google_directory__admin_import",
            )
        }
    ),
    tags={"job_type": "op"},
)
def google_directory_role_assignments_sync_job():
    role_assignments = bigquery_query_op()

    google_directory_role_assignment_create_op(role_assignments=role_assignments)
