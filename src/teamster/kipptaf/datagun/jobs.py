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


__all__ = [
    blissbook_extract_asset_job,
    clever_extract_asset_job,
    coupa_extract_asset_job,
    deanslist_extract_asset_job,
    egencia_extract_asset_job,
    idauto_extract_asset_job,
    illuminate_extract_asset_job,
    littlesis_extract_asset_job,
]

# RETIRED #
# adp_extract_asset_job = define_asset_job(
#     name="datagun_adp_extract_asset_job",
#     selection=AssetSelection.assets(*adp_extract_assets),
# )
# alchemer_extract_asset_job = define_asset_job(
#     name="datagun_alchemer_extract_asset_job",
#     selection=AssetSelection.assets(*alchemer_extract_assets),
# )
# fpodms_extract_asset_job = define_asset_job(
#     name="datagun_fpodms_extract_asset_job",
#     selection=AssetSelection.assets(*fpodms_extract_assets),
# )
# gam_extract_asset_job = define_asset_job(
#     name="datagun_gam_extract_asset_job",
#     selection=AssetSelection.assets(*gam_extract_assets),
# )
# gsheet_extract_asset_job = define_asset_job(
#     name="datagun_gsheet_extract_asset_job",
#     selection=AssetSelection.assets(*gsheet_extract_assets),
# )
# njdoe_extract_asset_job = define_asset_job(
#     name="datagun_njdoe_extract_asset_job",
#     selection=AssetSelection.assets(*njdoe_extract_assets),
# )
# razkids_extract_asset_job = define_asset_job(
#     name="datagun_razkids_extract_asset_job",
#     selection=AssetSelection.assets(*razkids_extract_assets),
# )
# read180_extract_asset_job = define_asset_job(
#     name="datagun_read180_extract_asset_job",
#     selection=AssetSelection.assets(*read180_extract_assets),
# )
# whetstone_extract_asset_job = define_asset_job(
#     name="datagun_whetstone_extract_asset_job",
#     selection=AssetSelection.assets(*whetstone_extract_assets),
# )
