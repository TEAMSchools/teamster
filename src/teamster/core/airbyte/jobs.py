from dagster import RunConfig, job
from dagster_airbyte.ops import AirbyteSyncConfig

from teamster.core.airbyte.ops import airbyte_start_sync_op


def build_airbyte_start_sync_job(code_location, connection_id, connection_name):
    @job(
        name=f"{code_location}_{connection_name}_airbyte_start_sync_job",
        config=RunConfig(
            ops={
                connection_name: AirbyteSyncConfig(
                    connection_id=connection_id, yield_materializations=False
                )
            }
        ),
    )
    def _job():
        airbyte_sync_op_aliased = airbyte_start_sync_op.alias(connection_name)
        airbyte_sync_op_aliased()

    return _job
