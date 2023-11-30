from dagster import RunConfig, define_asset_job, job

from teamster.core.google.bigquery.ops import (
    BigQueryGetTableOpConfig,
    bigquery_get_table_op,
)

from ... import CODE_LOCATION
from .assets import google_directory_nonpartitioned_assets
from .ops import (
    google_directory_member_create_op,
    google_directory_role_assignment_create_op,
    google_directory_user_create_op,
    google_directory_user_update_op,
)

google_directory_nonpartitioned_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_google_directory_nonpartitioned_asset_job",
    selection=[a.key for a in google_directory_nonpartitioned_assets],
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
)
def google_directory_role_assignments_sync_job():
    role_assignments = bigquery_get_table_op()

    google_directory_role_assignment_create_op(role_assignments=role_assignments)
