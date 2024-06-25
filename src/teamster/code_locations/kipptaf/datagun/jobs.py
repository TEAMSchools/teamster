from dagster import define_asset_job

from teamster.code_locations.kipptaf.datagun.assets import (
    blissbook_extract,
    clever_extract_assets,
    coupa_extract,
    deanslist_extract_assets,
    egencia_extract,
    idauto_extract,
    illuminate_extract_assets,
    littlesis_extract,
)

blissbook_extract_asset_job = define_asset_job(
    name="datagun_blissbook_extract_asset_job", selection=[blissbook_extract]
)

clever_extract_asset_job = define_asset_job(
    name="datagun_clever_extract_asset_job", selection=clever_extract_assets
)

coupa_extract_asset_job = define_asset_job(
    name="datagun_coupa_extract_asset_job", selection=[coupa_extract]
)

deanslist_extract_asset_job = define_asset_job(
    name="datagun_deanslist_extract_asset_job", selection=deanslist_extract_assets
)

egencia_extract_asset_job = define_asset_job(
    name="datagun_egencia_extract_asset_job", selection=[egencia_extract]
)

idauto_extract_asset_job = define_asset_job(
    name="datagun_idauto_extract_asset_job", selection=[idauto_extract]
)

illuminate_extract_asset_job = define_asset_job(
    name="datagun_illuminate_extract_asset_job", selection=illuminate_extract_assets
)

littlesis_extract_asset_job = define_asset_job(
    name="datagun_littlesis_extract_asset_job", selection=[littlesis_extract]
)

jobs = [
    blissbook_extract_asset_job,
    clever_extract_asset_job,
    coupa_extract_asset_job,
    deanslist_extract_asset_job,
    egencia_extract_asset_job,
    idauto_extract_asset_job,
    illuminate_extract_asset_job,
    littlesis_extract_asset_job,
]
