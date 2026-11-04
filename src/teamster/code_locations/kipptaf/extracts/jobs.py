from dagster import define_asset_job, in_process_executor

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.extracts.assets import (
    branchingminds_extract_assets,
    clever_extract_assets,
    coupa_extract,
    deanslist_annual_extract_assets,
    deanslist_continuous_extract,
    egencia_extract,
    idauto_extract,
    illuminate_extract_assets,
    lattice_extract,
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

lattice_extract_asset_job = define_asset_job(
    name=f"{lattice_extract.key.to_python_identifier()}__asset_job",
    selection=[lattice_extract],
)

littlesis_extract_asset_job = define_asset_job(
    name=f"{littlesis_extract.key.to_python_identifier()}__asset_job",
    selection=[littlesis_extract],
)

branchingminds_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__extracts__branchingminds__asset_job",
    selection=branchingminds_extract_assets,
)

# In process: a step pod per asset adds to the top-of-hour bursts that GKE
# preempts on new nodes (#6225). The steps are short, so loading the code location
# once and running them in turn takes about as long as parallel step pods, and the
# default run pod fits on an existing node.
clever_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__extracts__clever__asset_job",
    selection=clever_extract_assets,
    executor_def=in_process_executor,
)

deanslist_annual_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__extracts__deanslist_annual__asset_job",
    selection=deanslist_annual_extract_assets,
)

illuminate_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__extracts__illuminate__asset_job",
    selection=illuminate_extract_assets,
)
