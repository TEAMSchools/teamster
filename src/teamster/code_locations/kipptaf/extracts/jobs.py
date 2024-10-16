from dagster import define_asset_job

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.extracts.assets import (
    clever_extract_assets,
    coupa_extract,
    deanslist_annual_extract_assets,
    deanslist_continuous_extract,
    egencia_extract,
    idauto_extract,
    illuminate_extract_assets,
    littlesis_extract,
)

coupa_extract_asset_job = define_asset_job(
    name=f"{coupa_extract.key.to_python_identifier()}__asset_job",
    selection=[coupa_extract],
)

deanslist_continuous_extract_asset_job = define_asset_job(
    name=f"{deanslist_continuous_extract.key.to_python_identifier()}__asset_job",
    selection=[deanslist_continuous_extract],
)

egencia_extract_asset_job = define_asset_job(
    name=f"{egencia_extract.key.to_python_identifier()}__asset_job",
    selection=[egencia_extract],
)

idauto_extract_asset_job = define_asset_job(
    name=f"{idauto_extract.key.to_python_identifier()}__asset_job",
    selection=[idauto_extract],
)

littlesis_extract_asset_job = define_asset_job(
    name=f"{littlesis_extract.key.to_python_identifier()}__asset_job",
    selection=[littlesis_extract],
)

clever_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__extracts__clever__asset_job",
    selection=clever_extract_assets,
)

deanslist_annual_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__extracts__deanslist_annual__asset_job",
    selection=deanslist_annual_extract_assets,
)

illuminate_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__extracts__illuminate__asset_job",
    selection=illuminate_extract_assets,
)
