from dagster import MAX_RUNTIME_SECONDS_TAG, RunConfig, define_asset_job, job

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.schoolmint.grow.assets import (
    STATIC_PARTITONS_DEF,
    schoolmint_grow_assets_multi_partitions,
    schoolmint_grow_assets_static_partitions,
)
from teamster.libraries.google.bigquery.ops import (
    BigQueryGetTableOpConfig,
    bigquery_get_table_op,
)
from teamster.libraries.schoolmint.grow.ops import (
    schoolmint_grow_school_update_op,
    schoolmint_grow_user_update_op,
)


@job(
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


static_partition_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_schoolmint_grow_static_partition_asset_job",
    selection=schoolmint_grow_assets_static_partitions,
    partitions_def=STATIC_PARTITONS_DEF,
    tags={MAX_RUNTIME_SECONDS_TAG: (60 * 5)},
)

multi_partition_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_schoolmint_grow_multi_partition_asset_job",
    selection=schoolmint_grow_assets_multi_partitions,
    partitions_def=schoolmint_grow_assets_multi_partitions[0].partitions_def,
)

jobs = [
    static_partition_asset_job,
    multi_partition_asset_job,
    schoolmint_grow_user_update_job,
]
