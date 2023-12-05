from dagster import RunConfig, config_from_files, job
from dagster_airbyte.ops import AirbyteSyncConfig

from teamster.core.airbyte.ops import airbyte_start_sync_op

asset_config = config_from_files(["src/teamster/kipptaf/airbyte/config/assets.yaml"])[
    "assets"
]


@job(
    config=RunConfig(
        ops={
            asset["group_name"]: AirbyteSyncConfig(
                connection_id=asset["connection_id"], yield_materializations=False
            )
            for asset in asset_config
        }
    ),
)
def kipptaf_airbyte_start_syncs_job():
    for asset in asset_config:
        airbyte_sync_op_aliased = airbyte_start_sync_op.alias(asset["group_name"])

        airbyte_sync_op_aliased()


__all__ = [
    kipptaf_airbyte_start_syncs_job,
]
