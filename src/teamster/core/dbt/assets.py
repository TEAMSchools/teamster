from dagster import AssetIn, AssetsDefinition, OpExecutionContext, Output, asset
from dagster_dbt import DbtCliResource
from google.cloud import bigquery


def build_dbt_external_source_asset(asset_definition: AssetsDefinition):
    code_location, source_system, asset_name = asset_definition.key.path

    @asset(
        name=f"src_{source_system}__{asset_name}",
        ins={"upstream": AssetIn(key=[code_location, source_system, asset_name])},
        key_prefix=[code_location, "dbt", source_system],
        required_resource_keys={"warehouse_bq", "dbt"},
        partitions_def=asset_definition.partitions_def,
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
            args={"select": f"{dataset}.src_{source_system}__{asset_name}"},
            vars={"ext_full_refresh": True},
        )

        return Output(upstream, metadata=dbt_output.result)

    return _asset
