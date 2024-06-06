from dagster import build_op_context
from dagster_gcp import BigQueryResource

from teamster import GCS_PROJECT_NAME
from teamster.libraries.google.bigquery.ops import (
    BigQueryGetTableOpConfig,
    bigquery_get_table_op,
)
from teamster.libraries.google.directory.ops import (
    google_directory_role_assignment_create_op,
    google_directory_user_create_op,
    google_directory_user_update_op,
)
from teamster.libraries.google.directory.resources import GoogleDirectoryResource

GOOGLE_DIRECTORY_RESOURCE = GoogleDirectoryResource(
    customer_id="C029u7m0n",
    service_account_file_path="/etc/secret-volume/gcloud_service_account_json",
    delegated_account="dagster@apps.teamschools.org",
)

BIGQUERY_RESOURCE = BigQueryResource(project=GCS_PROJECT_NAME)

BIGQUERY_GET_TABLE_OP_CONFIG = BigQueryGetTableOpConfig(
    dataset_id="kipptaf_extracts", table_id="rpt_google_directory__users_import"
)


def test_google_directory_user_update_op():
    context = build_op_context()

    users = bigquery_get_table_op(
        context=context,
        db_bigquery=BIGQUERY_RESOURCE,
        config=BIGQUERY_GET_TABLE_OP_CONFIG,
    )

    google_directory_user_update_op(
        context=context, google_directory=GOOGLE_DIRECTORY_RESOURCE, users=users
    )


def test_google_directory_user_create_op():
    context = build_op_context()

    users = bigquery_get_table_op(
        context=context,
        db_bigquery=BIGQUERY_RESOURCE,
        config=BIGQUERY_GET_TABLE_OP_CONFIG,
    )

    google_directory_user_create_op(
        context=context, google_directory=GOOGLE_DIRECTORY_RESOURCE, users=users
    )


def test_google_directory_role_assignment_create_op():
    context = build_op_context()

    role_assignments = bigquery_get_table_op(
        context=context,
        db_bigquery=BIGQUERY_RESOURCE,
        config=BigQueryGetTableOpConfig(
            dataset_id="kipptaf_extracts", table_id="rpt_google_directory__admin_import"
        ),
    )

    google_directory_role_assignment_create_op(
        context=context,
        google_directory=GOOGLE_DIRECTORY_RESOURCE,
        role_assignments=role_assignments,
    )
