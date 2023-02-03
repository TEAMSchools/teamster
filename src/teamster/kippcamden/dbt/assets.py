from dagster_dbt import load_assets_from_dbt_project

dbt_assets = load_assets_from_dbt_project(
    project_dir="teamster-dbt",
    profiles_dir="teamster-dbt",
    key_prefix="dbt",
    source_key_prefix="dbt",
)
