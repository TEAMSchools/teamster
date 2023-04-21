from dagster import AssetSelection, define_asset_job

from .assets import (
    multi_partition_assets,
    multi_partitions_def,
    static_partition_assets,
    static_partitions_def,
)

static_partition_asset_job = define_asset_job(
    name="schoolmint_grow_static_partition_asset_job",
    selection=AssetSelection.assets(*static_partition_assets),
    partitions_def=static_partitions_def,
)

multi_partition_asset_job = define_asset_job(
    name="schoolmint_grow_multi_partition_asset_job",
    selection=AssetSelection.assets(*multi_partition_assets),
    partitions_def=multi_partitions_def,
)

__all__ = [
    static_partition_asset_job,
    multi_partition_asset_job,
]
