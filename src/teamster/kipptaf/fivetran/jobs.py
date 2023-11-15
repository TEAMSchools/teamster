import pathlib
import re

from dagster import RunConfig, config_from_files, job

from teamster.core.fivetran.jobs import build_fivetran_start_resync_job
from teamster.core.fivetran.ops import SyncConfig, fivetran_start_sync_op
from teamster.kipptaf import CODE_LOCATION, fivetran

fivetran_start_resync_jobs = []

for asset in fivetran.assets:
    op_name_match = re.match(pattern=r"fivetran_sync_(\w+)", string=asset.op.name)

    fivetran_start_resync_jobs.append(
        build_fivetran_start_resync_job(
            code_location=CODE_LOCATION,
            connector_id=op_name_match.group(1),
            connector_name=list(asset.keys)[0].path[1],
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


@job(
    config=RunConfig(
        ops={
            "adp_workforce_now": SyncConfig(
                connector_id="sameness_cunning", yield_materializations=False
            )
        }
    ),
)
def kipptaf_fivetran_adp_workforce_now_start_sync_job():
    fivetran_sync_op_aliased = fivetran_start_sync_op.alias("adp_workforce_now")

    fivetran_sync_op_aliased()


@job(
    config=RunConfig(
        ops={
            "illuminate": SyncConfig(
                connector_id="jinx_credulous", yield_materializations=False
            )
        }
    ),
)
def kipptaf_fivetran_illuminate_start_sync_job():
    fivetran_sync_op_aliased = fivetran_start_sync_op.alias("illuminate")

    fivetran_sync_op_aliased()


__all__ = [
    *fivetran_start_resync_jobs,
    kipptaf_fivetran_adp_workforce_now_start_sync_job,
    kipptaf_fivetran_illuminate_start_sync_job,
    kipptaf_fivetran_start_syncs_job,
]
