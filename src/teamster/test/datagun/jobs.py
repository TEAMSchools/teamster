from dagster import AssetSelection, define_asset_job

from teamster.test.datagun.assets import gsheet_extract_assets, sftp_extract_assets

test_extract_assets_job = define_asset_job(
    name="test_extract_assets_job",
    selection=AssetSelection.assets(*sftp_extract_assets, *gsheet_extract_assets),
)

__all__ = [test_extract_assets_job]
