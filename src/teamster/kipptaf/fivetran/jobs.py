from dagster import AssetSelection, define_asset_job

from teamster.kipptaf import CODE_LOCATION, fivetran

__all__ = []

for assets in fivetran.assets:
    for connector in assets.compute_cacheable_data():
        __all__.append(
            define_asset_job(
                name=f"{CODE_LOCATION}_fivetran_{connector.group_name}_asset_job",
                selection=AssetSelection.keys(
                    *[v for k, v in connector.keys_by_output_name.items()]
                ),
            )
        )
