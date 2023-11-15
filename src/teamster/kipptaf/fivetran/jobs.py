import pathlib
import re

from dagster import AssetSelection, RunConfig, config_from_files, define_asset_job, job

from teamster.core.fivetran.jobs import (
    build_fivetran_start_resync_job,
    build_fivetran_start_sync_job,
)
from teamster.core.fivetran.ops import SyncConfig, fivetran_start_sync_op
from teamster.kipptaf import CODE_LOCATION, fivetran

fivetran_materialization_jobs = []
fivetran_start_sync_jobs = []
fivetran_start_resync_jobs = []
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

    fivetran_start_resync_jobs.append(
        build_fivetran_start_resync_job(
            code_location=CODE_LOCATION,
            connector_id=connector_id,
            connector_name=connector_name,
        )
    )

asset_configs = [
    config_from_files([str(config)])
    for config in pathlib.Path("src/teamster/kipptaf/fivetran/config").glob("*.yaml")
]


@job(
    config=RunConfig(
        ops={
            config["connector_name"]: SyncConfig(
                connector_id=config["connector_id"], yield_materializations=False
            )
            for config in asset_configs
            if config["connector_name"] not in ["adp_workforce_now", "illuminate"]
        }
    ),
)
def kipptaf_fivetran_start_syncs_job():
    for config in asset_configs:
        connector_name = config["connector_name"]

        if connector_name not in ["adp_workforce_now", "illuminate"]:
            fivetran_sync_op_aliased = fivetran_start_sync_op.alias(connector_name)

            fivetran_sync_op_aliased()


__all__ = [
    *fivetran_materialization_jobs,
    *fivetran_start_sync_jobs,
    *fivetran_start_resync_jobs,
    kipptaf_fivetran_start_syncs_job,
]
