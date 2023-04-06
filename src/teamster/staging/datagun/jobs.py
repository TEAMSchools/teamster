from dagster import AssetSelection, define_asset_job

from . import assets

test_extract_asset_job = define_asset_job(
    name="datagun_test_extract_asset_job",
    selection=AssetSelection.assets(*assets.__all__),
)

__all__ = [
    test_extract_asset_job,
]
