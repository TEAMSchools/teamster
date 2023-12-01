from dagster import RunConfig, config_from_files, job
from dagster_airbyte.ops import AirbyteSyncConfig

from .. import CODE_LOCATION
from .ops import airbyte_start_sync_op

asset_config = config_from_files(
    ["src/teamster/{CODE_LOCATION}/airbyte/config/assets.yaml"]
)["assets"]


@job(
    name=f"{CODE_LOCATION}_airbyte_start_syncs_job",
    config=RunConfig(
        ops={
            asset["group_name"]: AirbyteSyncConfig(
                connection_id=asset["connection_id"], yield_materializations=False
            )
            for asset in asset_config
        }
    ),
)
def airbyte_start_syncs_job():
    for asset in asset_config:
        airbyte_sync_op_aliased = airbyte_start_sync_op.alias(asset["group_name"])

        airbyte_sync_op_aliased()
