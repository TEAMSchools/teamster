from dagster_dbt import load_assets_from_dbt_project

from teamster.core.dbt.assets import build_dbt_external_source_asset
from teamster.kippcamden import CODE_LOCATION
from teamster.kippcamden.powerschool.db.assets import whenmodified_assets

dbt_assets = load_assets_from_dbt_project(
    project_dir="teamster-dbt",
    profiles_dir="teamster-dbt",
    select="stg_assignmentcategoryassoc",
    key_prefix=[CODE_LOCATION, "dbt"],
    source_key_prefix=[CODE_LOCATION, "dbt"],
)

src_assignmentcategoryassoc = build_dbt_external_source_asset(whenmodified_assets[0])

__all__ = dbt_assets + [src_assignmentcategoryassoc]
