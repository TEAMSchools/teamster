from dagster import AssetSelection, define_asset_job

from teamster.kipptaf.datagun.assets import (
    adp_extract_assets,
    alchemer_extract_assets,
    blissbook_extract_assets,
    clever_extract_assets,
    coupa_extract_assets,
    deanslist_extract_assets,
    egencia_extract_assets,
    fpodms_extract_assets,
    gam_extract_assets,
    gsheet_extract_assets,
    idauto_extract_assets,
    illuminate_extract_assets,
    littlesis_extract_assets,
    njdoe_extract_assets,
    razkids_extract_assets,
    read180_extract_assets,
    whetstone_extract_assets,
)

adp_extract_assets_job = define_asset_job(
    name="adp_extract_assets_job",
    selection=AssetSelection.assets(*adp_extract_assets),
)

alchemer_extract_assets_job = define_asset_job(
    name="alchemer_extract_assets_job",
    selection=AssetSelection.assets(*alchemer_extract_assets),
)

blissbook_extract_assets_job = define_asset_job(
    name="blissbook_extract_assets_job",
    selection=AssetSelection.assets(*blissbook_extract_assets),
)

clever_extract_assets_job = define_asset_job(
    name="clever_extract_assets_job",
    selection=AssetSelection.assets(*clever_extract_assets),
)

coupa_extract_assets_job = define_asset_job(
    name="coupa_extract_assets_job",
    selection=AssetSelection.assets(*coupa_extract_assets),
)

deanslist_extract_assets_job = define_asset_job(
    name="deanslist_extract_assets_job",
    selection=AssetSelection.assets(*deanslist_extract_assets),
)

egencia_extract_assets_job = define_asset_job(
    name="egencia_extract_assets_job",
    selection=AssetSelection.assets(*egencia_extract_assets),
)

fpodms_extract_assets_job = define_asset_job(
    name="fpodms_extract_assets_job",
    selection=AssetSelection.assets(*fpodms_extract_assets),
)

gam_extract_assets_job = define_asset_job(
    name="gam_extract_assets_job",
    selection=AssetSelection.assets(*gam_extract_assets),
)

idauto_extract_assets_job = define_asset_job(
    name="idauto_extract_assets_job",
    selection=AssetSelection.assets(*idauto_extract_assets),
)

illuminate_extract_assets_job = define_asset_job(
    name="illuminate_extract_assets_job",
    selection=AssetSelection.assets(*illuminate_extract_assets),
)

littlesis_extract_assets_job = define_asset_job(
    name="littlesis_extract_assets_job",
    selection=AssetSelection.assets(*littlesis_extract_assets),
)

njdoe_extract_assets_job = define_asset_job(
    name="njdoe_extract_assets_job",
    selection=AssetSelection.assets(*njdoe_extract_assets),
)

razkids_extract_assets_job = define_asset_job(
    name="razkids_extract_assets_job",
    selection=AssetSelection.assets(*razkids_extract_assets),
)

read180_extract_assets_job = define_asset_job(
    name="read180_extract_assets_job",
    selection=AssetSelection.assets(*read180_extract_assets),
)

whetstone_extract_assets_job = define_asset_job(
    name="whetstone_extract_assets_job",
    selection=AssetSelection.assets(*whetstone_extract_assets),
)

gsheet_extract_assets_job = define_asset_job(
    name="gsheet_extract_assets_job",
    selection=AssetSelection.assets(*gsheet_extract_assets),
)
