from dagster import AssetSelection, define_asset_job

from teamster.core.airbyte.jobs import build_airbyte_start_sync_job
from teamster.staging import CODE_LOCATION, airbyte

airbyte_materialization_jobs = []
airbyte_start_sync_jobs = []
for asset in airbyte.assets:
    connection_name = list(asset.group_names_by_key.values())[0]
    connection_id = list(
        set([m["connection_id"] for m in asset.metadata_by_key.values()])
    )[0]

    airbyte_materialization_jobs.append(
        define_asset_job(
            name=(f"{CODE_LOCATION}_airbyte_{connection_name}_asset_job"),
            selection=AssetSelection.keys(*list(asset.keys)),
        )
    )

    airbyte_start_sync_jobs.append(
        build_airbyte_start_sync_job(
            code_location=CODE_LOCATION,
            connection_id=connection_id,
            connection_name=connection_name,
        )
    )

__all__ = [
    *airbyte_materialization_jobs,
    *airbyte_start_sync_jobs,
]
