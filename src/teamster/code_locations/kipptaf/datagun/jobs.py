from dagster import define_asset_job

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.datagun.assets import (
    clever_extract_assets,
    coupa_extract,
    deanslist_annual_extract_assets,
    deanslist_continuous_extract,
    egencia_extract,
    idauto_extract,
    illuminate_extract_assets,
    littlesis_extract,
)

clever_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_datagun_clever_extract_asset_job",
    selection=clever_extract_assets,
)

coupa_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_datagun_coupa_extract_asset_job", selection=[coupa_extract]
)

deanslist_annual_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_datagun_deanslist_annual_extract_asset_job",
    selection=deanslist_annual_extract_assets,
)

deanslist_continuous_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_datagun_deanslist_continuous_extract_asset_job",
    selection=[deanslist_continuous_extract],
)

egencia_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_datagun_egencia_extract_asset_job",
    selection=[egencia_extract],
)

idauto_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_datagun_idauto_extract_asset_job", selection=[idauto_extract]
)

illuminate_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_datagun_illuminate_extract_asset_job",
    selection=illuminate_extract_assets,
)

littlesis_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_datagun_littlesis_extract_asset_job",
    selection=[littlesis_extract],
)
