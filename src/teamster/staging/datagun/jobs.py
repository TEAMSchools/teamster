from dagster import AssetSelection, define_asset_job

from .assets import gsheet_extract_assets, sftp_extract_assets

test_extract_asset_job = define_asset_job(
    name="datagun_test_extract_asset_job",
    selection=AssetSelection.assets(*gsheet_extract_assets, *sftp_extract_assets),
)

__all__ = [
    test_extract_asset_job,
]
