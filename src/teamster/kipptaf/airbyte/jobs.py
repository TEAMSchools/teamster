from dagster import AssetSelection, define_asset_job

from teamster.kipptaf import CODE_LOCATION, airbyte

__all__ = []

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
