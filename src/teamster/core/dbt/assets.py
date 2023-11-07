import json
from typing import Any, Mapping

from dagster import (
    AssetExecutionContext,
    AssetKey,
    AssetOut,
    Nothing,
    Output,
    multi_asset,
)
from dagster_dbt import DagsterDbtTranslator, DbtCliResource
from dagster_dbt.asset_utils import (
    DAGSTER_DBT_TRANSLATOR_METADATA_KEY,
    MANIFEST_METADATA_KEY,
)
from dagster_dbt.dagster_dbt_translator import DbtManifestWrapper


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


def build_dbt_external_source_assets(code_location, manifest, dagster_dbt_translator):
    external_sources = [
        source
        for source in manifest["sources"].values()
        if "stage_external_sources" in source["tags"]
    ]

    outs = {
        source["name"]: AssetOut(
            key=dagster_dbt_translator.get_asset_key(source),
            group_name=source["source_name"],
            dagster_type=Nothing,
            description=dagster_dbt_translator.get_description(source),
            is_required=False,
            metadata={
                **dagster_dbt_translator.get_metadata(source),
                MANIFEST_METADATA_KEY: DbtManifestWrapper(manifest=manifest),
                DAGSTER_DBT_TRANSLATOR_METADATA_KEY: dagster_dbt_translator,
            },
        )
        for source in external_sources
    }

    deps = []
    internal_asset_deps = {}
    for source in external_sources:
        source_name = source["source_name"]
        table_name = source["name"]

        dep_key = source["meta"].get("dagster", {}).get("dep_key")

        if dep_key is None:
            dep_key_prefix = source["fqn"][1:-2]

            if not dep_key_prefix:
                dep_key_prefix = [source_name]

            identifier = source["identifier"]

            if identifier[-3:].lower() == "__c":
                dep_name = identifier
            else:
                dep_name = identifier.split("__")[-1]

            dep_key = AssetKey([code_location, *dep_key_prefix, dep_name])
        else:
            dep_key = AssetKey(dep_key)

        deps.append(dep_key)

        internal_asset_deps[table_name] = set([dep_key])

    @multi_asset(
        name="dbt_external_source_assets",
        outs=outs,
        deps=deps,
        internal_asset_deps=internal_asset_deps,
        compute_kind="dbt",
        can_subset=True,
        op_tags={"dagster-dbt/select": "tag:stage_external_sources"},
    )
    def _assets(context: AssetExecutionContext, dbt_cli: DbtCliResource):
        source_selection = [
            f"{context.assets_def.group_names_by_key[asset_key]}.{asset_key.path[-1]}"
            for asset_key in context.selected_asset_keys
        ]

        # run dbt stage_external_sources
        dbt_run_operation = dbt_cli.cli(
            args=[
                "run-operation",
                "stage_external_sources",
                "--args",
                json.dumps({"select": " ".join(source_selection)}),
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
