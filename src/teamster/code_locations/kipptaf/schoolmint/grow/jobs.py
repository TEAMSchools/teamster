from dagster import RunConfig, define_asset_job, job

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.schoolmint.grow.assets import (
    observations,
    schoolmint_grow_static_partition_assets,
)
from teamster.libraries.google.bigquery.ops import (
    BigQueryGetTableOpConfig,
    bigquery_get_table_op,
)
from teamster.libraries.schoolmint.grow.ops import (
    schoolmint_grow_school_update_op,
    schoolmint_grow_user_update_op,
)

schoolmint_grow_static_partition_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__schoolmint__grow__static_partition_asset_job",
    selection=schoolmint_grow_static_partition_assets,
)

schoolmint_grow_observations_asset_job = define_asset_job(
    name=f"{observations.key.to_python_identifier()}_job",
    selection=[observations],
    partitions_def=observations.partitions_def,
)


@job(
    name=f"{CODE_LOCATION}__schoolmint__grow__user_update_job",
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
