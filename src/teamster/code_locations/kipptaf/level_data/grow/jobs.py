from dagster import RunConfig, define_asset_job, job

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.level_data.grow.assets import (
    grow_static_partition_assets,
    observations,
)
from teamster.libraries.google.bigquery.ops import BigQueryOpConfig, bigquery_query_op
from teamster.libraries.level_data.grow.ops import (
    grow_school_update_op,
    grow_user_update_op,
)

grow_static_partition_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__grow__static_partition_asset_job",
    selection=grow_static_partition_assets,
)

grow_observations_asset_job = define_asset_job(
    name=f"{observations.key.to_python_identifier()}_job",
    selection=[observations],
    partitions_def=observations.partitions_def,
)


@job(
    name=f"{CODE_LOCATION}__grow__user_update_job",
    config=RunConfig(
        ops={
            "bigquery_query_op": BigQueryOpConfig(
                dataset_id="kipptaf_extracts", table_id="rpt_schoolmint_grow__users"
            )
        }
    ),
    tags={"job_type": "op"},
)
def grow_user_update_job():
    users = bigquery_query_op()

    updated_users = grow_user_update_op(users=users)

    grow_school_update_op(users=updated_users)
