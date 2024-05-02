import json
from typing import Any, Callable

from dagster import (
    AssetExecutionContext,
    AssetsDefinition,
    BackfillPolicy,
    DagsterInvalidDefinitionError,
    Output,
    PartitionsDefinition,
    TimeWindowPartitionsDefinition,
    multi_asset,
)
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, dbt_assets
from dagster_dbt.asset_decorator import get_dbt_multi_asset_args
from dagster_dbt.asset_utils import (
    DAGSTER_DBT_EXCLUDE_METADATA_KEY,
    DAGSTER_DBT_SELECT_METADATA_KEY,
    get_deps,
)
from dagster_dbt.dagster_dbt_translator import validate_translator
from dagster_dbt.dbt_manifest import DbtManifestParam, validate_manifest
from dagster_dbt.utils import (
    get_dbt_resource_props_by_dbt_unique_id_from_manifest,
    select_unique_ids_from_manifest,
)


def build_dbt_assets(
    manifest, dagster_dbt_translator, select="fqn:*", exclude=None, partitions_def=None
):
    @dbt_assets(
        manifest=manifest,
        dagster_dbt_translator=dagster_dbt_translator,
        select=select,
        exclude=exclude,
        partitions_def=partitions_def,
    )
    def _assets(context: AssetExecutionContext, dbt_cli: DbtCliResource):
        dbt_build = dbt_cli.cli(args=["build"], context=context)

        yield from dbt_build.stream()

    return _assets


def build_dbt_external_source_assets(
    manifest, dagster_dbt_translator, select="fqn:*", exclude=None, partitions_def=None
):
    @dbt_assets(
        manifest=manifest,
        dagster_dbt_translator=dagster_dbt_translator,
        select=select,
        exclude=exclude,
        partitions_def=partitions_def,
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
            dagster_dbt_translator=dagster_dbt_translator,
        )

        for event in dbt_run_operation.stream_raw_events():
            context.log.info(event)

        for output_name in context.selected_output_names:
            yield Output(value=None, output_name=output_name)

    return _assets


def dbt_external_source_assets(
    *,
    manifest: DbtManifestParam,
    select: str = "fqn:*",
    exclude: str | None = None,
    name: str | None = None,
    io_manager_key: str | None = None,
    partitions_def: PartitionsDefinition | None = None,
    dagster_dbt_translator: DagsterDbtTranslator | None = None,
    backfill_policy: BackfillPolicy | None = None,
    op_tags: dict[str, Any] | None = None,
    required_resource_keys: set[str] | None = None,
) -> Callable[[Callable[..., Any]], AssetsDefinition]:
    """
    Forked from dagster_dbt.asset_decorator.dbt_assets
    """
    dagster_dbt_translator = validate_translator(
        dagster_dbt_translator or DagsterDbtTranslator()
    )
    manifest = validate_manifest(manifest)

    unique_ids = select_unique_ids_from_manifest(
        select=select, exclude=exclude or "", manifest_json=manifest
    )
    node_info_by_dbt_unique_id = get_dbt_resource_props_by_dbt_unique_id_from_manifest(
        manifest
    )

    dbt_unique_id_deps = get_deps(
        dbt_nodes=node_info_by_dbt_unique_id,
        selected_unique_ids=unique_ids,
        asset_resource_types=["source"],
    )

    (
        deps,
        outs,
        internal_asset_deps,
        check_specs,
    ) = get_dbt_multi_asset_args(
        dbt_nodes=node_info_by_dbt_unique_id,
        dbt_unique_id_deps=dbt_unique_id_deps,
        io_manager_key=io_manager_key,
        manifest=manifest,
        dagster_dbt_translator=dagster_dbt_translator,
    )

    if op_tags and DAGSTER_DBT_SELECT_METADATA_KEY in op_tags:
        raise DagsterInvalidDefinitionError(
            "To specify a dbt selection, use the 'select' argument, not '"
            f"{DAGSTER_DBT_SELECT_METADATA_KEY}' with op_tags"
        )

    if op_tags and DAGSTER_DBT_EXCLUDE_METADATA_KEY in op_tags:
        raise DagsterInvalidDefinitionError(
            "To specify a dbt exclusion, use the 'exclude' argument, not '"
            f"{DAGSTER_DBT_EXCLUDE_METADATA_KEY}' with op_tags"
        )

    resolved_op_tags = {
        **({DAGSTER_DBT_SELECT_METADATA_KEY: select} if select else {}),
        **({DAGSTER_DBT_EXCLUDE_METADATA_KEY: exclude} if exclude else {}),
        **(op_tags if op_tags else {}),
    }

    if (
        partitions_def
        and isinstance(partitions_def, TimeWindowPartitionsDefinition)
        and not backfill_policy
    ):
        backfill_policy = BackfillPolicy.single_run()

    return multi_asset(
        outs=outs,
        name=name,
        internal_asset_deps=internal_asset_deps,
        deps=deps,
        required_resource_keys=required_resource_keys,
        compute_kind="dbt",
        partitions_def=partitions_def,
        can_subset=True,
        op_tags=resolved_op_tags,
        check_specs=check_specs,
        backfill_policy=backfill_policy,
    )


"""
def build_dbt_external_source_assets(
    code_location, manifest, dagster_dbt_translator: CustomDagsterDbtTranslator
):
    replace with select param
    external_sources = [
        source
        for source in manifest["sources"].values()
        if "stage_external_sources" in source["tags"]
    ]

    outs = {
        source["name"]: AssetOut(
            key=dagster_dbt_translator.get_asset_key(source),
            group_name=dagster_dbt_translator.get_group_name(source),
            dagster_type=Nothing,
            description=dagster_dbt_translator.get_description(source),
            is_required=False,
            metadata={
                **dagster_dbt_translator.get_metadata(source),
                DAGSTER_DBT_MANIFEST_METADATA_KEY: DbtManifestWrapper(
                    manifest=manifest
                ),
                DAGSTER_DBT_TRANSLATOR_METADATA_KEY: dagster_dbt_translator,
            },  # type: ignore
            auto_materialize_policy=AutoMaterializePolicy.eager().without_rules(
                AutoMaterializeRule.skip_on_parent_missing(),
                AutoMaterializeRule.materialize_on_required_for_freshness(),
            ),
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
            dagster_dbt_translator=dagster_dbt_translator,
        )

        for event in dbt_run_operation.stream_raw_events():
            context.log.info(event)

        for output_name in context.selected_output_names:
            yield Output(value=None, output_name=output_name)

    return _assets
"""
