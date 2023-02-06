from dagster_dbt import load_assets_from_dbt_project

from teamster.core.dbt.assets import build_dbt_external_source_asset
from teamster.kippcamden import CODE_LOCATION

dbt_assets = load_assets_from_dbt_project(
    project_dir="teamster-dbt",
    profiles_dir="teamster-dbt",
    select=f"{CODE_LOCATION}",
    key_prefix=[CODE_LOCATION, "dbt"],
    source_key_prefix=[CODE_LOCATION, "dbt"],
)

src_assignmentcategoryassoc = build_dbt_external_source_asset(
    asset_name="assignmentcategoryassoc",
    code_location=CODE_LOCATION,
    source_system="powerschool",
)
