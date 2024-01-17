import pathlib

from dagster import RunConfig, config_from_files, job
from dagster_airbyte.ops import AirbyteSyncConfig

from .. import CODE_LOCATION
from .ops import airbyte_start_sync_op

asset_config = config_from_files(
    [f"{pathlib.Path(__file__).parent}/config/assets.yaml"]
)["assets"]


@job(
    name=f"{CODE_LOCATION}_airbyte_start_syncs_job",
    config=RunConfig(
        ops={
            asset["group_name"]: AirbyteSyncConfig(
                connection_id=asset["connection_id"], yield_materializations=False
            )  # type: ignore
            for asset in asset_config
        }
    ),
    tags={"job_type": "op"},
)
def airbyte_start_syncs_job():
    for asset in asset_config:
        airbyte_sync_op_aliased = airbyte_start_sync_op.alias(asset["group_name"])

        airbyte_sync_op_aliased()


_all = [
    airbyte_start_syncs_job,
]
