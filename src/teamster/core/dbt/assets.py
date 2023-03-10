import json

from dagster import AssetIn, AssetsDefinition, OpExecutionContext, Output, asset
from dagster_dbt import DbtCliResource, load_assets_from_dbt_manifest
from google.cloud import bigquery

from teamster.core.utils.functions import partition_key_to_vars


def build_external_source_asset(asset_definition: AssetsDefinition):
    code_location, package_name, asset_name = asset_definition.key.path

    @asset(
        name=f"src_{package_name}__{asset_name}",
        key_prefix=[code_location, "dbt", package_name],
        ins={"upstream": AssetIn(key=[code_location, package_name, asset_name])},
        required_resource_keys={"bq", "dbt"},
        compute_kind="dbt",
        group_name="staging",
    )
    def _asset(context: OpExecutionContext, upstream):
        dataset_name = f"{code_location}_{package_name}"

        # create BigQuery dataset, if not exists
        bq: bigquery.Client = context.resources.bq
        context.log.info(f"Creating dataset {dataset_name}")
        bq.create_dataset(dataset=dataset_name, exists_ok=True)

        # dbt run-operation stage_external_sources
        dbt: DbtCliResource = context.resources.dbt

        dbt_output = dbt.run_operation(
            macro="stage_external_sources",
            args={"select": f"{package_name}.src_{package_name}__{asset_name}"},
            vars={"ext_full_refresh": True},
        )

        return Output(upstream, metadata=dbt_output.result)

    return _asset


def build_staging_assets(
    manifest_json_path, key_prefix, assets: list[AssetsDefinition]
):
    with open(file=manifest_json_path) as f:
        manifest_json = json.load(f)

    asset_lists = [
        load_assets_from_dbt_manifest(
            manifest_json=manifest_json,
            select=f"stg_{asset.key.path[-2]}__{asset.key.path[-1]}+",
            key_prefix=key_prefix,
            source_key_prefix=key_prefix,
            partitions_def=asset.partitions_def,
            partition_key_to_vars_fn=(
                partition_key_to_vars if asset.partitions_def is not None else None
            ),
        )
        for asset in assets
    ]

    return [asset for asset_list in asset_lists for asset in asset_list]
