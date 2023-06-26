import json

from dagster import (
    AssetExecutionContext,
    AssetKey,
    AssetOut,
    AssetsDefinition,
    asset,
    multi_asset,
)
from dagster_dbt import load_assets_from_dbt_manifest
from dagster_dbt.asset_decorator import dbt_assets
from dagster_dbt.cli import DbtCli, DbtCliClientResource
from dagster_gcp import BigQueryResource


def build_dbt_assets(manifest):
    @dbt_assets(manifest=manifest)
    def _assets(context: AssetExecutionContext, dbt_cli: DbtCli):
        yield from dbt_cli.cli(
            args=["build"], manifest=manifest, context=context
        ).stream()

    return _assets


def build_external_source_asset_new(
    code_location,
    name,
    dbt_package_name,
    upstream_asset_key,
    group_name,
    manifest,
):
    @asset(
        name=name,
        key_prefix=[code_location, "dbt", dbt_package_name],
        non_argument_deps=[upstream_asset_key],
        compute_kind="dbt",
        group_name=group_name,
    )
    def _asset(
        context: AssetExecutionContext, dbt_cli: DbtCli, db_bigquery: BigQueryResource
    ):
        dataset_name = f"{code_location}_{dbt_package_name}"

        # create BigQuery dataset, if not exists
        context.log.info(f"Creating dataset {dataset_name}")
        with db_bigquery.get_client() as bq:
            bq.create_dataset(dataset=dataset_name, exists_ok=True)

        # stage_external_sources
        yield from dbt_cli.cli(
            args=[
                "run_operation",
                "stage_external_sources",
                "--args",
                f"{{'select': '{name}'}}",
                "--vars",
                "'ext_full_refresh: true'",
            ],
            manifest=manifest,
            context=context,
        ).stream()

    return _asset


def build_staging_asset_from_source(
    code_location,
    dbt_package_name,
    source_model_name,
    staging_model_name,
    upstream_asset_key: AssetKey,
    group_name,
    manifest,
):
    key_prefix = [code_location, "dbt", dbt_package_name]

    @multi_asset(
        outs={
            source_model_name: AssetOut(key_prefix=key_prefix),
            staging_model_name: AssetOut(key_prefix=key_prefix),
        },
        name=f"{upstream_asset_key.to_python_identifier()}__dbt",
        non_argument_deps=[upstream_asset_key],
        compute_kind="dbt",
        group_name=group_name,
    )
    def _asset(
        context: AssetExecutionContext, dbt_cli: DbtCli, db_bigquery: BigQueryResource
    ):
        dataset_name = f"{code_location}_{dbt_package_name}"

        # create BigQuery dataset, if not exists
        context.log.info(f"Creating dataset {dataset_name}")
        with db_bigquery.get_client() as bq:
            bq.create_dataset(dataset=dataset_name, exists_ok=True)

        # stage_external_sources
        yield from dbt_cli.cli(
            args=[
                "run_operation",
                "stage_external_sources",
                "--args",
                f"{'select': '{source_model_name}'}",
                "--vars",
                "'ext_full_refresh: true'",
            ],
            manifest=manifest,
            context=context,
        ).stream()

        # build staging model
        yield from dbt_cli.cli(
            args=["build", "--select", staging_model_name],
            manifest=manifest,
            context=context,
        ).stream()

    return _asset


def build_external_source_asset(asset_definition: AssetsDefinition):
    code_location, package_name, asset_name = asset_definition.key.path

    @asset(
        name=f"src_{package_name}__{asset_name}",
        key_prefix=[code_location, "dbt", package_name],
        non_argument_deps=[AssetKey([code_location, package_name, asset_name])],
        compute_kind="dbt",
        group_name="staging",
    )
    def _asset(
        context: AssetExecutionContext,
        db_bigquery: BigQueryResource,
        dbt: DbtCliClientResource,
    ):
        dataset_name = f"{code_location}_{package_name}"

        # create BigQuery dataset, if not exists
        context.log.info(f"Creating dataset {dataset_name}")
        with db_bigquery.get_client() as bq:
            bq.create_dataset(dataset=dataset_name, exists_ok=True)

        dbt.get_dbt_client().run_operation(
            macro="stage_external_sources",
            args={"select": f"{package_name}.src_{package_name}__{asset_name}"},
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
