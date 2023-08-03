from dagster import define_asset_job

from .assets import google_forms_assets

google_forms_asset_job = define_asset_job(
    name="google_forms_asset_job", selection=[a.key for a in google_forms_assets]
)

__all__ = [
    google_forms_asset_job,
]
