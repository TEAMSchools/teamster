from dagster import RunConfig, define_asset_job, job

from ...google.bigquery.ops import BigQueryGetTableOpConfig, bigquery_get_table_op
from .assets import multi_partition_assets, static_partition_assets
from .ops import schoolmint_grow_school_update_op, schoolmint_grow_user_update_op


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
    name="schoolmint_grow_static_partition_asset_job",
    selection=static_partition_assets,
    partitions_def=static_partition_assets[0].partitions_def,
)

multi_partition_asset_job = define_asset_job(
    name="schoolmint_grow_multi_partition_asset_job",
    selection=multi_partition_assets,
    partitions_def=multi_partition_assets[0].partitions_def,
)

_all = [
    static_partition_asset_job,
    multi_partition_asset_job,
    schoolmint_grow_user_update_job,
]
