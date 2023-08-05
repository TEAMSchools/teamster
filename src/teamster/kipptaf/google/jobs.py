from dagster import RunConfig, define_asset_job, job

from teamster.core.google.bigquery.ops import (
    BigQueryGetTableOpConfig,
    bigquery_get_table_op,
)

from .assets import google_forms_assets
from .ops import google_directory_user_create_op, google_directory_user_update_op

google_forms_asset_job = define_asset_job(
    name="google_forms_asset_job", selection=[a.key for a in google_forms_assets]
)


@job(
    config=RunConfig(
        ops={
            "bigquery_get_table_op": BigQueryGetTableOpConfig(
                dataset_id="kipptaf_extracts", table_id="rpt_schoolmint_grow__users"
            )
        }
    )
)
def google_directory_user_sync_job():
    users = bigquery_get_table_op()

    google_directory_user_create_op(users=users)
    google_directory_user_update_op(users=users)


__all__ = [
    google_forms_asset_job,
    google_directory_user_sync_job,
]
