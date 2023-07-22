from dagster import RunConfig, job

from teamster.core.fivetran.ops import SyncConfig, fivetran_start_sync_op


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
