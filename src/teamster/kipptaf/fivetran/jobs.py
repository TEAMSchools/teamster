import pathlib

from dagster import RunConfig, config_from_files, job

from .. import CODE_LOCATION
from .ops import (
    FivetranResyncConfig,
    SyncConfig,
    fivetran_start_resync_op,
    fivetran_start_sync_op,
)


@job(
    name=f"{CODE_LOCATION}_fivetran_adp_workforce_now_start_resync_job",
    config=RunConfig(
        ops={
            "fivetran_start_resync_op": FivetranResyncConfig(
                connector_id="sameness_cunning", yield_materializations=False
            )
        }
    ),
    tags={"job_type": "op"},
)
def fivetran_adp_workforce_now_start_resync_job():
    fivetran_start_resync_op()


@job(
    name=f"{CODE_LOCATION}_fivetran_adp_workforce_now_start_sync_job",
    config=RunConfig(
        ops={
            "fivetran_start_sync_op": SyncConfig(
                connector_id="sameness_cunning", yield_materializations=False
            )
        }
    ),
    tags={"job_type": "op"},
)
def fivetran_adp_workforce_now_start_sync_job():
    fivetran_start_sync_op()


@job(
    name=f"{CODE_LOCATION}_fivetran_illuminate_start_sync_job",
    config=RunConfig(
        ops={
            "fivetran_start_sync_op": SyncConfig(
                connector_id="jinx_credulous", yield_materializations=False
            )
        }
    ),
    tags={"job_type": "op"},
)
def fivetran_illuminate_start_sync_job():
    fivetran_start_sync_op()


asset_configs = [
    config_from_files([str(config)])
    for config in pathlib.Path("src/teamster/kipptaf/fivetran/config").glob("*.yaml")
]


@job(
    name=f"{CODE_LOCATION}_fivetran_start_syncs_job",
    config=RunConfig(
        ops={
            config["connector_name"]: SyncConfig(
                connector_id=config["connector_id"], yield_materializations=False
            )
            for config in asset_configs
            if config["connector_name"] not in ["adp_workforce_now", "illuminate"]
        }
    ),
    tags={"job_type": "op"},
)
def fivetran_start_syncs_job():
    for config in asset_configs:
        connector_name = config["connector_name"]

        if connector_name not in ["adp_workforce_now", "illuminate"]:
            fivetran_sync_op_aliased = fivetran_start_sync_op.alias(connector_name)
            fivetran_sync_op_aliased()


_all = [
    fivetran_adp_workforce_now_start_resync_job,
    fivetran_adp_workforce_now_start_sync_job,
    fivetran_illuminate_start_sync_job,
    fivetran_start_syncs_job,
]
