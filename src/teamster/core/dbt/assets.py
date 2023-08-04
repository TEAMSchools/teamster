import json
import pathlib
from typing import Any, Mapping

from dagster import (
    AssetExecutionContext,
    AssetKey,
    AssetOut,
    Nothing,
    Output,
    asset,
    multi_asset,
)
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, dbt_assets
from dagster_dbt.asset_utils import (
    DAGSTER_DBT_TRANSLATOR_METADATA_KEY,
    MANIFEST_METADATA_KEY,
)
from dagster_dbt.dagster_dbt_translator import DbtManifestWrapper
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

            # components.insert(0, "dbt")
            components.insert(0, code_location)

            return AssetKey(components)

    return CustomDagsterDbtTranslator


def build_dbt_assets(code_location):
    dagster_dbt_translator = get_custom_dagster_dbt_translator(code_location)
    manifest_file = pathlib.Path(f"src/dbt/{code_location}/target/manifest.json")

    manifest = json.loads(s=manifest_file.read_text())

    @dbt_assets(
        manifest=manifest,
        exclude="tag:stage_external_sources",
        dagster_dbt_translator=dagster_dbt_translator(),
    )
    def _assets(context: AssetExecutionContext, dbt_cli: DbtCliResource):
        dbt_build = dbt_cli.cli(args=["build"], context=context)

        yield from dbt_build.stream()

    return _assets


def build_dbt_external_source_assets(code_location):
    dagster_dbt_translator = get_custom_dagster_dbt_translator(code_location)
    manifest_file = pathlib.Path(f"src/dbt/{code_location}/target/manifest.json")

    manifest = json.loads(s=manifest_file.read_text())

    outs = {}
    internal_asset_deps = {}
    deps = []
    for source in manifest["sources"].values():
        if "stage_external_sources" not in source["tags"]:
            continue

        source_name = source["source_name"]
        table_name = source["name"]
        key_prefix = source["fqn"][1:-2]

        if not key_prefix:
            key_prefix = [source["source_name"]]

        identifier = source["identifier"]

        if identifier[-3:].lower() == "__c":
            dep_name = identifier
        else:
            dep_name = identifier.split("__")[-1]

        out_key = dagster_dbt_translator.get_asset_key(source)

        asset_out = AssetOut(
            key=out_key,
            group_name=source_name,
            dagster_type=Nothing,
            description=dagster_dbt_translator.get_description(source),
            is_required=False,
            metadata={
                **dagster_dbt_translator.get_metadata(source),
                MANIFEST_METADATA_KEY: DbtManifestWrapper(manifest=manifest),
                DAGSTER_DBT_TRANSLATOR_METADATA_KEY: dagster_dbt_translator,
                "dataset": source["schema"],
            },
        )
        dep_key = AssetKey([code_location, *key_prefix, dep_name])
        deps_set = set()

        deps.append(dep_key)
        deps_set.add(dep_key)

        outs[table_name] = asset_out
        internal_asset_deps[table_name] = deps_set

    @multi_asset(
        name="dbt_external_source_assets",
        outs=outs,
        deps=deps,
        internal_asset_deps=internal_asset_deps,
        compute_kind="dbt",
        can_subset=True,
        op_tags={"dagster-dbt/select": "tag:stage_external_sources"},
    )
    def _assets(
        context: AssetExecutionContext,
        db_bigquery: BigQueryResource,
        dbt_cli: DbtCliResource,
    ):
        with db_bigquery.get_client() as bq:
            bq_client = bq

        for output_name in context.selected_output_names:
            metadata = context.get_output_metadata(output_name=output_name)

            bq_client.create_dataset(dataset=metadata["dataset"], exists_ok=True)

        dbt_run_operation = dbt_cli.cli(
            args=[
                "run-operation",
                "stage_external_sources",
                "--vars",
                json.dumps({"ext_full_refresh": True}),
            ],
            manifest=manifest,
            dagster_dbt_translator=dagster_dbt_translator(),
        )

        for event in dbt_run_operation.stream_raw_events():
            context.log.info(event)

        for output_name in context.selected_output_names:
            yield Output(value=None, output_name=output_name)

    return _assets


def build_external_source_asset(
    code_location, name, dbt_package_name, upstream_asset_key, group_name
):
    dagster_dbt_translator = get_custom_dagster_dbt_translator(code_location)
    manifest_file = pathlib.Path(f"src/dbt/{code_location}/target/manifest.json")

    manifest = json.loads(s=manifest_file.read_text())

    @asset(
        key=[code_location, dbt_package_name, name],
        deps=[upstream_asset_key],
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
            dagster_dbt_translator=dagster_dbt_translator(),
        )

        for event in dbt_run_operation.stream_raw_events():
            context.log.info(event)

    return _asset
