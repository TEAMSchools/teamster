from dagster import AssetSelection, define_asset_job, job

from teamster.core.airbyte.ops import build_airbyte_materialization_op
from teamster.kipptaf import CODE_LOCATION, airbyte

airbyte_materialization_op = build_airbyte_materialization_op(asset_defs=airbyte.assets)


@job
def airbyte_materialization_job():
    airbyte_materialization_op()


__all__ = [
    airbyte_materialization_job,
]

for asset in airbyte.assets:
    __all__.append(
        define_asset_job(
            name=(
                f"{CODE_LOCATION}_airbyte_"
                f"{list(asset.group_names_by_key.values())[0]}_asset_job"
            ),
            selection=AssetSelection.keys(*list(asset.keys)),
        )
    )
