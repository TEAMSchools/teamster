import re

from dagster import AssetSelection, define_asset_job

from teamster.core.fivetran.jobs import build_fivetran_start_sync_job
from teamster.kipptaf import CODE_LOCATION, fivetran

fivetran_materialization_jobs = []
fivetran_start_sync_jobs = []
for asset in fivetran.assets:
    connector_name = list(asset.keys)[0].path[1]
    connector_id = re.match(
        pattern=r"fivetran_sync_(\w+)",
        string=asset.op.name,
    ).group(1)

    fivetran_materialization_jobs.append(
        define_asset_job(
            name=(f"{CODE_LOCATION}_{connector_name}_fivetran_asset_job"),
            selection=AssetSelection.keys(*list(asset.keys)),
        )
    )

    fivetran_start_sync_jobs.append(
        build_fivetran_start_sync_job(
            code_location=CODE_LOCATION,
            connector_id=connector_id,
            connector_name=connector_name,
        )
    )

__all__ = [
    *fivetran_materialization_jobs,
    *fivetran_start_sync_jobs,
]
