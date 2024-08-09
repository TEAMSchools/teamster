from dagster import RunConfig, job

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.libraries.google.bigquery.ops import (
    BigQueryGetTableOpConfig,
    bigquery_get_table_op,
)
from teamster.libraries.google.directory.ops import (
    google_directory_member_create_op,
    google_directory_role_assignment_create_op,
    google_directory_user_create_op,
    google_directory_user_update_op,
)


@job(
    name=f"{CODE_LOCATION}_google_directory_user_sync_job",
    config=RunConfig(
        ops={
            "bigquery_get_table_op": BigQueryGetTableOpConfig(
                dataset_id="kipptaf_extracts",
                table_id="rpt_google_directory__users_import",
            )
        }
    ),
    tags={"job_type": "op"},
)
def google_directory_user_sync_job():
    users = bigquery_get_table_op()

    members = google_directory_user_create_op(users=users)
    google_directory_user_update_op(users=users)

    google_directory_member_create_op(members=members)


@job(
    name=f"{CODE_LOCATION}_google_directory_role_assignments_sync_job",
    config=RunConfig(
        ops={
            "bigquery_get_table_op": BigQueryGetTableOpConfig(
                dataset_id="kipptaf_extracts",
                table_id="rpt_google_directory__admin_import",
            )
        }
    ),
    tags={"job_type": "op"},
)
def google_directory_role_assignments_sync_job():
    role_assignments = bigquery_get_table_op()

    google_directory_role_assignment_create_op(role_assignments=role_assignments)
