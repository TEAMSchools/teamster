from dagster import RunConfig, job

from teamster.core.fivetran.ops import (
    FivetranResyncConfig,
    SyncConfig,
    fivetran_start_resync_op,
    fivetran_start_sync_op,
)


def build_fivetran_start_sync_job(code_location, connector_id, connector_name):
    @job(
        name=f"{code_location}_{connector_name}_fivetran_start_sync_job",
        config=RunConfig(
            ops={
                connector_name: SyncConfig(
                    connector_id=connector_id, yield_materializations=False
                )
            }
        ),
    )
    def _job():
        fivetran_sync_op_aliased = fivetran_start_sync_op.alias(connector_name)
        fivetran_sync_op_aliased()

    return _job


def build_fivetran_start_resync_job(code_location, connector_id, connector_name):
    @job(
        name=f"{code_location}_{connector_name}_fivetran_start_resync_job",
        config=RunConfig(
            ops={
                connector_name: FivetranResyncConfig(
                    connector_id=connector_id, yield_materializations=False
                )
            }
        ),
    )
    def _job():
        fivetran_resync_op_aliased = fivetran_start_resync_op.alias(connector_name)
        fivetran_resync_op_aliased()

    return _job
