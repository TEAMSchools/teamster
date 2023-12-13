from dagster import AssetSelection, define_asset_job

from .assets import (
    blissbook_extract_assets,
    clever_extract_assets,
    coupa_extract_assets,
    deanslist_extract_assets,
    egencia_extract_assets,
    idauto_extract_assets,
    illuminate_extract_assets,
    littlesis_extract_assets,
)

blissbook_extract_asset_job = define_asset_job(
    name="datagun_blissbook_extract_asset_job",
    selection=AssetSelection.assets(*blissbook_extract_assets),
)

clever_extract_asset_job = define_asset_job(
    name="datagun_clever_extract_asset_job",
    selection=AssetSelection.assets(*clever_extract_assets),
)

coupa_extract_asset_job = define_asset_job(
    name="datagun_coupa_extract_asset_job",
    selection=AssetSelection.assets(*coupa_extract_assets),
)

deanslist_extract_asset_job = define_asset_job(
    name="datagun_deanslist_extract_asset_job",
    selection=AssetSelection.assets(*deanslist_extract_assets),
)

egencia_extract_asset_job = define_asset_job(
    name="datagun_egencia_extract_asset_job",
    selection=AssetSelection.assets(*egencia_extract_assets),
)


idauto_extract_asset_job = define_asset_job(
    name="datagun_idauto_extract_asset_job",
    selection=AssetSelection.assets(*idauto_extract_assets),
)

illuminate_extract_asset_job = define_asset_job(
    name="datagun_illuminate_extract_asset_job",
    selection=AssetSelection.assets(*illuminate_extract_assets),
)

littlesis_extract_asset_job = define_asset_job(
    name="datagun_littlesis_extract_asset_job",
    selection=AssetSelection.assets(*littlesis_extract_assets),
)


_all = [
    blissbook_extract_asset_job,
    clever_extract_asset_job,
    coupa_extract_asset_job,
    deanslist_extract_asset_job,
    egencia_extract_asset_job,
    idauto_extract_asset_job,
    illuminate_extract_asset_job,
    littlesis_extract_asset_job,
]
