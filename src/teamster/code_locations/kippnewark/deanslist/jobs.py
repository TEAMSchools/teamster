from dagster import define_asset_job

from teamster.code_locations.kippnewark.deanslist.assets import (
    multi_partition_fiscal_assets,
    multi_partition_monthly_assets,
    static_partition_assets,
)

static_partition_asset_job = define_asset_job(
    name="deanslist_static_partition_asset_job",
    selection=static_partition_assets,
    partitions_def=static_partition_assets[0].partitions_def,
)

multi_partition_monthly_asset_job = define_asset_job(
    name="deanslist_multi_partition_monthly_asset_job",
    selection=multi_partition_monthly_assets,
    partitions_def=multi_partition_monthly_assets[0].partitions_def,
)

multi_partition_fiscal_asset_job = define_asset_job(
    name="deanslist_multi_partition_fiscal_asset_job",
    selection=multi_partition_fiscal_assets,
    partitions_def=multi_partition_fiscal_assets[0].partitions_def,
)

jobs = [
    static_partition_asset_job,
    multi_partition_monthly_asset_job,
    multi_partition_fiscal_asset_job,
]
