import json
from typing import Any, Mapping

from dagster import AssetExecutionContext, AssetKey, Failure, Output, asset
from dagster_dbt import DagsterDbtTranslator, DbtCliResource
from dagster_dbt.asset_decorator import dbt_assets
from dagster_gcp import BigQueryResource


def get_custom_dagster_dbt_translator(code_location):
    class CustomDagsterDbtTranslator(DagsterDbtTranslator):
        @classmethod
        def get_asset_key(cls, dbt_resource_props: Mapping[str, Any]) -> AssetKey:
            node_info = dbt_resource_props

            dagster_metadata = node_info.get("meta", {}).get("dagster", {})
            asset_key_config = dagster_metadata.get("asset_key", [])
            if asset_key_config:
                return AssetKey(asset_key_config)

            if node_info["resource_type"] == "source":
                components = [node_info["source_name"], node_info["name"]]
            else:
                configured_schema = node_info["config"].get("schema")
                if configured_schema is not None:
                    components = [configured_schema, node_info["name"]]
                else:
                    components = [node_info["name"]]

            components.insert(0, code_location)

            return AssetKey(components)

    return CustomDagsterDbtTranslator


def build_dbt_assets(code_location):
    dagster_dbt_translator = get_custom_dagster_dbt_translator(code_location)

    with open(file=f"src/dbt/{code_location}/target/manifest.json") as fp:
        manifest = json.load(fp=fp)

    @dbt_assets(manifest=manifest)
    def _assets(context: AssetExecutionContext, dbt_cli: DbtCliResource):
        dbt_build = dbt_cli.cli(
            args=["build"],
            dagster_dbt_translator=dagster_dbt_translator,
            context=context,
        )

        yield from dbt_build.stream()

    return _assets


def build_external_source_asset(
    code_location, name, dbt_package_name, upstream_asset_key, group_name
):
    dagster_dbt_translator = get_custom_dagster_dbt_translator(code_location)

    with open(file=f"src/dbt/{code_location}/target/manifest.json") as fp:
        manifest = json.load(fp=fp)

    @asset(
        key=[code_location, dbt_package_name, name],
        non_argument_deps=[upstream_asset_key],
        compute_kind="dbt",
        group_name=group_name,
    )
    def _asset(
        context: AssetExecutionContext,
        dbt_cli: DbtCliResource,
        db_bigquery: BigQueryResource,
    ):
        dataset_name = f"{code_location}_{dbt_package_name}"

        # create BigQuery dataset, if not exists
        context.log.info(f"Creating dataset {dataset_name}")
        with db_bigquery.get_client() as bq:
            bq.create_dataset(dataset=dataset_name, exists_ok=True)

        # stage_external_sources
        dbt_run_operation = dbt_cli.cli(
            args=[
                "run-operation",
                "stage_external_sources",
                "--args",
                json.dumps({"select": f"{dbt_package_name}.{name}"}),
                "--vars",
                json.dumps({"ext_full_refresh": True}),
            ],
            manifest=manifest,
            dagster_dbt_translator=dagster_dbt_translator,
            context=context,
        )

        for event in dbt_run_operation.stream_raw_events():
            context.log.info(event)

        if dbt_run_operation.is_successful():
            return Output(value=True)
        else:
            raise Failure()

    return _asset
