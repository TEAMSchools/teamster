from dagster_dbt import load_assets_from_dbt_project

dbt_assets = load_assets_from_dbt_project(
    project_dir="dbt", profiles_dir="dbt", key_prefix="dbt", source_key_prefix="dbt"
)
