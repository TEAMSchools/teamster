from dagster import build_op_context
from dagster_gcp import BigQueryResource

from teamster.core.google.bigquery.ops import (
    BigQueryGetTableOpConfig,
    bigquery_get_table_op,
)
from teamster.core.google.directory.resources import GoogleDirectoryResource
from teamster.kipptaf import GCS_PROJECT_NAME
from teamster.kipptaf.google.ops import (
    google_directory_user_create_op,
    google_directory_user_update_op,
)


def test_google_directory_user_update_op():
    context = build_op_context()

    users = bigquery_get_table_op(
        context=context,
        db_bigquery=BigQueryResource(project=GCS_PROJECT_NAME),
        config=BigQueryGetTableOpConfig(
            dataset_id="kipptaf_extracts", table_id="rpt_google_directory__users_import"
        ),
    )

    google_directory_user_update_op(
        context=context,
        google_directory=GoogleDirectoryResource(
            customer_id="C029u7m0n",
            service_account_file_path="/etc/secret-volume/gcloud_service_account_json",
            delegated_account="dagster@apps.teamschools.org",
        ),
        users=users,
    )


def test_google_directory_user_create_op():
    context = build_op_context()

    users = bigquery_get_table_op(
        context=context,
        db_bigquery=BigQueryResource(project=GCS_PROJECT_NAME),
        config=BigQueryGetTableOpConfig(
            dataset_id="kipptaf_extracts", table_id="rpt_google_directory__users_import"
        ),
    )

    google_directory_user_create_op(
        context=context,
        google_directory=GoogleDirectoryResource(
            customer_id="C029u7m0n",
            service_account_file_path="/etc/secret-volume/gcloud_service_account_json",
            delegated_account="dagster@apps.teamschools.org",
        ),
        users=users,
    )
