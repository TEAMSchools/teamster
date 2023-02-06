from dagster import AssetIn, OpExecutionContext, Output, asset
from dagster_dbt import DbtCliResource, load_assets_from_dbt_project
from google.cloud import bigquery

from teamster.kippcamden import CODE_LOCATION

dbt_assets = load_assets_from_dbt_project(
    project_dir="teamster-dbt",
    profiles_dir="teamster-dbt",
    select=f"{CODE_LOCATION}",
    key_prefix=[CODE_LOCATION, "dbt"],
    source_key_prefix=[CODE_LOCATION, "dbt"],
)


def build_dbt_external_source_asset(asset_name, code_location, source_system):
    @asset(
        name=f"src_{asset_name}",
        ins={"upstream": AssetIn(key=[code_location, source_system, asset_name])},
        key_prefix=[code_location, "dbt", f"{code_location}_{source_system}"],
        required_resource_keys={"warehouse_bq", "dbt"},
    )
    def _asset(context: OpExecutionContext, upstream):
        dataset = f"{code_location}_{source_system}"

        # create BigQuery dataset, if not exists
        bq: bigquery.Client = context.resources.warehouse_bq
        context.log.debug(f"Creating dataset {dataset}")
        bq.create_dataset(dataset=dataset, exists_ok=True)

        # dbt run-operation stage_external_sources
        dbt: DbtCliResource = context.resources.dbt

        dbt_output = dbt.run_operation(
            macro="stage_external_sources",
            args={"select": f"{dataset}.src_{asset_name}"},
            vars={"ext_full_refresh": True},
        )

        return Output(dbt_output)

    return _asset


src_assignmentcategoryassoc = build_dbt_external_source_asset(
    asset_name="assignmentcategoryassoc",
    code_location=CODE_LOCATION,
    source_system="powerschool",
)
