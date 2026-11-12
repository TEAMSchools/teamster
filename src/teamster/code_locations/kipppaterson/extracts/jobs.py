from dagster import define_asset_job, in_process_executor

from teamster.code_locations.kipppaterson import CODE_LOCATION
from teamster.code_locations.kipppaterson.extracts.assets import (
    powerschool_extract_assets,
)

powerschool_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__extracts__powerschool__asset_job",
    selection=powerschool_extract_assets,
    executor_def=in_process_executor,
)
