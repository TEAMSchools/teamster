from dagster import AssetSelection, define_asset_job, job

from teamster.kipptaf import CODE_LOCATION, fivetran

__all__ = []

for asset in fivetran.assets:
    __all__.append(
        define_asset_job(
            name=(
                f"{CODE_LOCATION}_fivetran_"
                f"{list(asset.group_names_by_key.values())[0]}_asset_job"
            ),
            selection=AssetSelection.keys(*list(asset.keys)),
        )
    )


@job
def _job():
    ...
