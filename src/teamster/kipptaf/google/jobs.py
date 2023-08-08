from dagster import RunConfig, define_asset_job, job

from teamster.core.google.bigquery.ops import (
    BigQueryGetTableOpConfig,
    bigquery_get_table_op,
)

from .assets import google_directory_nonpartitioned_assets, google_forms_assets
from .ops import (
    google_directory_member_create_op,
    google_directory_role_assignment_create_op,
    google_directory_user_create_op,
    google_directory_user_update_op,
)

google_forms_asset_job = define_asset_job(
    name="google_forms_asset_job", selection=[a.key for a in google_forms_assets]
)

google_directory_nonpartitioned_asset_job = define_asset_job(
    name="google_directory_nonpartitioned_asset_job",
    selection=[a.key for a in google_directory_nonpartitioned_assets],
)


@job(
    config=RunConfig(
        ops={
            "bigquery_get_table_op": BigQueryGetTableOpConfig(
                dataset_id="kipptaf_extracts",
                table_id="rpt_google_directory__users_import",
            )
        }
    )
)
def google_directory_user_sync_job():
    users = bigquery_get_table_op()

    members = google_directory_user_create_op(users=users)
    google_directory_user_update_op(users=users)

    google_directory_member_create_op(members=members)


@job(
    config=RunConfig(
        ops={
            "bigquery_get_table_op": BigQueryGetTableOpConfig(
                dataset_id="kipptaf_extracts",
                table_id="rpt_google_directory__admin_import",
            )
        }
    )
)
def google_directory_role_assignments_sync_job():
    role_assignments = bigquery_get_table_op()

    google_directory_role_assignment_create_op(role_assignments=role_assignments)


__all__ = [
    google_directory_nonpartitioned_asset_job,
    google_directory_role_assignments_sync_job,
    google_directory_user_sync_job,
    google_forms_asset_job,
]
