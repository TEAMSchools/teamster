from dagster import EnvVar, build_op_context
from dagster_gcp import BigQueryResource

from teamster.core.schoolmint.grow.resources import SchoolMintGrowResource
from teamster.kipptaf import GCS_PROJECT_NAME
from teamster.kipptaf.schoolmint.ops import (
    schoolmint_grow_get_user_update_data_op,
    schoolmint_grow_user_update_op,
)


def test_op():
    context = build_op_context()

    users = schoolmint_grow_get_user_update_data_op(
        context=context, db_bigquery=BigQueryResource(project=GCS_PROJECT_NAME)
    )

    schoolmint_grow_user_update_op(
        context=context,
        schoolmint_grow=SchoolMintGrowResource(
            client_id=EnvVar("SCHOOLMINT_GROW_CLIENT_ID"),
            client_secret=EnvVar("SCHOOLMINT_GROW_CLIENT_SECRET"),
            district_id=EnvVar("SCHOOLMINT_GROW_DISTRICT_ID"),
            api_response_limit=3200,
        ),
        users=users,
    )
