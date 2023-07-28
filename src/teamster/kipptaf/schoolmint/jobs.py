from dagster import AssetSelection, define_asset_job, job

from .assets import multi_partition_assets, static_partition_assets
from .ops import schoolmint_grow_get_user_update_data_op, schoolmint_grow_user_update_op

static_partition_asset_job = define_asset_job(
    name="schoolmint_grow_static_partition_asset_job",
    selection=AssetSelection.assets(*static_partition_assets),
    partitions_def=static_partition_assets[0].partitions_def,
)

multi_partition_asset_job = define_asset_job(
    name="schoolmint_grow_multi_partition_asset_job",
    selection=AssetSelection.assets(*multi_partition_assets),
    partitions_def=multi_partition_assets[0].partitions_def,
)


@job
def schoolmint_grow_user_update_job():
    users = schoolmint_grow_get_user_update_data_op()

    schoolmint_grow_user_update_op(users)


__all__ = [
    static_partition_asset_job,
    multi_partition_asset_job,
    schoolmint_grow_user_update_job,
]
