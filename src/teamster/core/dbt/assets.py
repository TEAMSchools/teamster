import json

from dagster import (
    AssetExecutionContext,
    AssetIn,
    AssetKey,
    AssetsDefinition,
    Output,
    asset,
)
from dagster_dbt import DbtCliClientResource, load_assets_from_dbt_manifest

# from dagster_dbt.cli import DbtCli, DbtManifest
from dagster_gcp import BigQueryResource

"""
def build_staging_assets_from_source(manifest: DbtManifest, select="fqn:*", exclude=""):
    @asset(
        name=f"src_{dbt_package_name}__{table_name}",
        key_prefix=[code_location, "dbt", dbt_package_name],
        ins={
            "upstream": AssetIn(
                key=[
                    code_location,
                    upstream_package_name,
                    f"{dbt_package_name}__{table_name}",
                ]
            )
        },
        compute_kind="dbt",
        group_name=group_name,
    )
    def _asset(
        context: AssetExecutionContext, dbt: DbtCli, db_bigquery: BigQueryResource
    ):
        dataset_name = f"{code_location}_{package_name}"

        # create BigQuery dataset, if not exists
        context.log.info(f"Creating dataset {dataset_name}")
        with db_bigquery.get_client() as bq:
            bq.create_dataset(dataset=dataset_name, exists_ok=True)

        yield dbt.cli(
            args=[
                "stage_external_sources",
                "--args"
                f"{'select': '{package_name}.src_{package_name}__{asset_name}'}",
                "--vars",
                "'ext_full_refresh: true'",
            ],
            manifest=manifest,
            context=context,
        ).stream()

        yield dbt.cli(args=["run"])

    return _asset
"""


def build_external_source_asset(asset_definition: AssetsDefinition):
    code_location, package_name, asset_name = asset_definition.key.path

    @asset(
        name=f"src_{package_name}__{asset_name}",
        key_prefix=[code_location, "dbt", package_name],
        ins={"upstream": AssetIn(key=[code_location, package_name, asset_name])},
        compute_kind="dbt",
        group_name="staging",
    )
    def _asset(
        context: AssetExecutionContext,
        db_bigquery: BigQueryResource,
        dbt: DbtCliClientResource,
        upstream,
    ):
        dataset_name = f"{code_location}_{package_name}"

        # create BigQuery dataset, if not exists
        context.log.info(f"Creating dataset {dataset_name}")
        with db_bigquery.get_client() as bq:
            bq.create_dataset(dataset=dataset_name, exists_ok=True)

        dbt_output = dbt.get_dbt_client().run_operation(
            macro="stage_external_sources",
            args={"select": f"{package_name}.src_{package_name}__{asset_name}"},
            vars="ext_full_refresh: true",
        )

        return Output(value=upstream, metadata=dbt_output.result)

    return _asset


def build_external_source_asset_from_key(asset_key: AssetKey):
    code_location, package_name, asset_name = asset_key.path

    @asset(
        name=f"src_{package_name}__{asset_name}",
        key_prefix=[code_location, "dbt", package_name],
        ins={"upstream": AssetIn(key=[code_location, package_name, asset_name])},
        compute_kind="dbt",
        group_name=package_name,
    )
    def _asset(
        context: AssetExecutionContext,
        db_bigquery: BigQueryResource,
        dbt: DbtCliClientResource,
        upstream,
    ):
        dataset_name = f"{code_location}_{package_name}"

        # create BigQuery dataset, if not exists
        context.log.info(f"Creating dataset {dataset_name}")
        with db_bigquery.get_client() as bq:
            bq.create_dataset(dataset=dataset_name, exists_ok=True)

        dbt_output = dbt.get_dbt_client().run_operation(
            macro="stage_external_sources",
            args={"select": f"{package_name}.src_{package_name}__{asset_name}"},
            vars="ext_full_refresh: true",
        )

        return Output(value=upstream, metadata=dbt_output.result)

    return _asset


def build_external_source_asset_from_params(
    code_location, table_name, dbt_package_name, upstream_package_name, group_name
):
    @asset(
        name=f"src_{dbt_package_name}__{table_name}",
        key_prefix=[code_location, "dbt", dbt_package_name],
        non_argument_deps=[
            AssetKey(
                [
                    code_location,
                    upstream_package_name,
                    f"{dbt_package_name}__{table_name}",
                ]
            )
        ],
        compute_kind="dbt",
        group_name=group_name,
    )
    def _asset(
        context: AssetExecutionContext,
        db_bigquery: BigQueryResource,
        dbt: DbtCliClientResource,
    ):
        dataset_name = f"{code_location}_{dbt_package_name}"

        # create BigQuery dataset, if not exists
        context.log.info(f"Creating dataset {dataset_name}")
        with db_bigquery.get_client() as bq:
            bq.create_dataset(dataset=dataset_name, exists_ok=True)

        dbt.get_dbt_client().run_operation(
            macro="stage_external_sources",
            args={"select": f"src_{dbt_package_name}__{table_name}"},
            vars="ext_full_refresh: true",
        )

    return _asset


def build_staging_assets(
    manifest_json_path, key_prefix, assets: list[AssetsDefinition]
):
    with open(file=manifest_json_path) as f:
        manifest_json = json.load(f)

    asset_lists = [
        load_assets_from_dbt_manifest(
            manifest_json=manifest_json,
            select=f"stg_{asset.key.path[-2]}__{asset.key.path[-1]}",
            key_prefix=key_prefix,
            source_key_prefix=key_prefix,
        )
        for asset in assets
    ]

    return [asset for asset_list in asset_lists for asset in asset_list]
