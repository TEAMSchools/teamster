from dagster import AssetSelection, define_asset_job

from teamster.kippcamden.deanslist import assets

deanslist_school_partition_assets_job = define_asset_job(
    name="deanslist_nonpartition_assets_job",
    selection=AssetSelection.assets(*assets.school_partition_assets),
    partitions_def=assets.static_partitions_def,
)

deanslist_multi_partition_assets_job = define_asset_job(
    name="deanslist_partition_assets_job",
    selection=AssetSelection.assets(*assets.multi_partition_assets),
    partitions_def=assets.multi_partitions_def,
)

__all__ = [deanslist_school_partition_assets_job, deanslist_multi_partition_assets_job]
