from dagster import AssetSelection, define_asset_job

from teamster.kippcamden.deanslist import assets

deanslist_nonpartition_assets_job = define_asset_job(
    name="deanslist_nonpartition_assets_job",
    selection=AssetSelection.assets(*assets.nonpartition_assets),
)

deanslist_partition_assets_job = define_asset_job(
    name="deanslist_partition_assets_job",
    selection=AssetSelection.assets(*assets.partition_assets),
    partitions_def=assets.multi_partitions_def,
)

__all__ = [deanslist_nonpartition_assets_job, deanslist_partition_assets_job]
