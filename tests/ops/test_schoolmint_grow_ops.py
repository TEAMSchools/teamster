from dagster import EnvVar, build_op_context
from dagster_gcp import BigQueryResource

from teamster import GCS_PROJECT_NAME
from teamster.libraries.google.bigquery.ops import (
    BigQueryGetTableOpConfig,
    bigquery_get_table_op,
    bigquery_query_op,
)
from teamster.libraries.schoolmint.grow.ops import (
    schoolmint_grow_school_update_op,
    schoolmint_grow_user_delete_op,
    schoolmint_grow_user_update_op,
)
from teamster.libraries.schoolmint.grow.resources import SchoolMintGrowResource

SCHOOLMINT_GROW = SchoolMintGrowResource(
    client_id=EnvVar("SCHOOLMINT_GROW_CLIENT_ID"),
    client_secret=EnvVar("SCHOOLMINT_GROW_CLIENT_SECRET"),
    district_id=EnvVar("SCHOOLMINT_GROW_DISTRICT_ID"),
    api_response_limit=3200,
)

DB_BIGQUERY = BigQueryResource(project=GCS_PROJECT_NAME)


def test_user_update_job():
    context = build_op_context()

    users = bigquery_get_table_op(context=context, db_bigquery=DB_BIGQUERY)

    updated_users = schoolmint_grow_user_update_op(
        context=context, schoolmint_grow=SCHOOLMINT_GROW, users=users
    )

    schoolmint_grow_school_update_op(
        context=context, schoolmint_grow=SCHOOLMINT_GROW, users=updated_users
    )


def test_user_deactivate_job():
    context = build_op_context()

    users = bigquery_query_op(
        context=context,
        db_bigquery=DB_BIGQUERY,
        config=BigQueryGetTableOpConfig(
            dataset_id="adhoc", table_id="schoolmint_grow_user_delete"
        ),
    )

    schoolmint_grow_user_delete_op(
        context=context, schoolmint_grow=SCHOOLMINT_GROW, users=users
    )
