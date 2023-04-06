from dagster import AssetSelection, define_asset_job

from . import assets

static_partition_asset_job = define_asset_job(
    name="schoolmint_grow_static_partition_assets_job",
    selection=AssetSelection.assets(*assets.static_partition_assets),
    # partitions_def=assets.static_partitions_def,
)

multi_partition_asset_job = define_asset_job(
    name="schoolmint_grow_multi_partition_assets_job",
    selection=AssetSelection.assets(*assets.multi_partition_assets),
    # partitions_def=assets.multi_partitions_def,
)

__all__ = [
    static_partition_asset_job,
    multi_partition_asset_job,
]
