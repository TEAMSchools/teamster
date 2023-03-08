from dagster import AssetSelection, define_asset_job

from . import assets

deanslist_static_partition_assets_job = define_asset_job(
    name="deanslist_school_partition_assets_job",
    selection=AssetSelection.assets(*assets.static_partition_assets),
    partitions_def=assets.static_partitions_def,
)

deanslist_multi_partition_assets_job = define_asset_job(
    name="deanslist_multi_partition_assets_job",
    selection=AssetSelection.assets(*assets.multi_partition_assets),
    partitions_def=assets.multi_partitions_def,
)

__all__ = [
    deanslist_static_partition_assets_job,
    deanslist_multi_partition_assets_job,
]
