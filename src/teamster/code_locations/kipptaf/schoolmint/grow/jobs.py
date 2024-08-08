from dagster import RunConfig, job

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.libraries.google.bigquery.ops import (
    BigQueryGetTableOpConfig,
    bigquery_get_table_op,
)
from teamster.libraries.schoolmint.grow.ops import (
    schoolmint_grow_school_update_op,
    schoolmint_grow_user_update_op,
)


@job(
    name=f"{CODE_LOCATION}__schoolmint_grow__user_update_job",
    config=RunConfig(
        ops={
            "bigquery_get_table_op": BigQueryGetTableOpConfig(
                dataset_id="kipptaf_extracts", table_id="rpt_schoolmint_grow__users"
            )
        }
    ),
    tags={"job_type": "op"},
)
def schoolmint_grow_user_update_job():
    users = bigquery_get_table_op()

    updated_users = schoolmint_grow_user_update_op(users=users)

    schoolmint_grow_school_update_op(users=updated_users)
