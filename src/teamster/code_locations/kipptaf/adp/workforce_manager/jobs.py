from dagster import define_asset_job

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.adp.workforce_manager.assets import (
    adp_wfm_assets_daily,
    adp_wfm_assets_dynamic,
)

adp_wfm_daily_partition_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_adp_wfm_daily_partition_asset_job",
    selection=adp_wfm_assets_daily,
    partitions_def=adp_wfm_assets_daily[0].partitions_def,
)

adp_wfm_dynamic_partition_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_adp_wfm_dynamic_partition_asset_job",
    selection=adp_wfm_assets_dynamic,
    partitions_def=adp_wfm_assets_dynamic[0].partitions_def,
)

jobs = [
    adp_wfm_daily_partition_asset_job,
    adp_wfm_dynamic_partition_asset_job,
]
