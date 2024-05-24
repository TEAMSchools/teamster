from typing import Any, Callable, Mapping, Sequence

from dagster import (
    AssetDep,
    AssetKey,
    AssetsDefinition,
    BackfillPolicy,
    DagsterInvalidDefinitionError,
    PartitionsDefinition,
    TimeWindowPartitionsDefinition,
    multi_asset,
)
from dagster_dbt import DagsterDbtTranslator, DbtProject
from dagster_dbt.asset_decorator import (
    DUPLICATE_ASSET_KEY_ERROR_MESSAGE,
    get_dbt_multi_asset_args,
)
from dagster_dbt.asset_utils import (
    DAGSTER_DBT_EXCLUDE_METADATA_KEY,
    DAGSTER_DBT_SELECT_METADATA_KEY,
    get_deps,
)
from dagster_dbt.dagster_dbt_translator import validate_translator
from dagster_dbt.dbt_manifest import DbtManifestParam, validate_manifest
from dagster_dbt.utils import (
    dagster_name_fn,
    get_dbt_resource_props_by_dbt_unique_id_from_manifest,
    select_unique_ids_from_manifest,
)


def get_dbt_multi_asset_deps(
    dbt_nodes: Mapping[str, Any],
    dbt_unique_id_deps: Mapping[str, frozenset[str]],
    dagster_dbt_translator: DagsterDbtTranslator,
) -> tuple[Sequence[AssetDep], dict[str, set[AssetKey]]]:
    """Forked from dagster_dbt.asset_decorator.get_dbt_multi_asset_args"""
    deps: set[AssetDep] = set()
    internal_asset_deps: dict[str, set[AssetKey]] = {}

    dbt_unique_id_and_resource_types_by_asset_key: dict[
        AssetKey, tuple[set[str], set[str]]
    ] = {}

    for unique_id in dbt_unique_id_deps.keys():
        dbt_resource_props = dbt_nodes[unique_id]

        output_name = dagster_name_fn(dbt_resource_props)
        asset_key = dagster_dbt_translator.get_asset_key(dbt_resource_props)

        # Translate parent unique ids to dependencies
        output_internal_deps = internal_asset_deps.setdefault(output_name, set())

        parent_asset_key_path = (
            dbt_resource_props.get("meta", {})
            .get("dagster", {})
            .get("parent_asset_key_path")
        )

        if parent_asset_key_path is not None:
            parent_asset_key = AssetKey(parent_asset_key_path)

            # Add this parent as an internal dependency
            output_internal_deps.add(parent_asset_key)

            # Mark this parent as an input if it has no dependencies
            deps.add(AssetDep(asset=parent_asset_key))

    dbt_unique_ids_by_duplicate_asset_key = {
        asset_key: sorted(unique_ids)
        for asset_key, (
            unique_ids,
            resource_types,
        ) in dbt_unique_id_and_resource_types_by_asset_key.items()
        if len(unique_ids) != 1
        and not (
            resource_types == set(["source"])
            and dagster_dbt_translator.settings.enable_duplicate_source_asset_keys
        )
    }

    if dbt_unique_ids_by_duplicate_asset_key:
        error_messages = []

        for asset_key, unique_ids in dbt_unique_ids_by_duplicate_asset_key.items():
            formatted_ids = []

            for id in unique_ids:
                unique_id_file_path = dbt_nodes[id]["original_file_path"]
                formatted_ids.append(f"  - `{id}` ({unique_id_file_path})")

            error_messages.append(
                "\n".join(
                    [
                        "The following dbt resources have the asset key "
                        + f"`{asset_key.path}`:",
                        *formatted_ids,
                    ]
                )
            )

        raise DagsterInvalidDefinitionError(
            "\n\n".join([DUPLICATE_ASSET_KEY_ERROR_MESSAGE, *error_messages])
        )

    return list(deps), internal_asset_deps


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
    project: DbtProject | None = None,
) -> Callable[[Callable[..., Any]], AssetsDefinition]:
    """Forked from dagster_dbt.asset_decorator.dbt_assets"""
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
        _deps,
        outs,
        _internal_asset_deps,
        check_specs,
    ) = get_dbt_multi_asset_args(
        dbt_nodes=node_info_by_dbt_unique_id,
        dbt_unique_id_deps=dbt_unique_id_deps,
        io_manager_key=io_manager_key,
        manifest=manifest,
        dagster_dbt_translator=dagster_dbt_translator,
        project=project,
    )

    deps, internal_asset_deps = get_dbt_multi_asset_deps(
        dbt_nodes=node_info_by_dbt_unique_id,
        dbt_unique_id_deps=dbt_unique_id_deps,
        dagster_dbt_translator=dagster_dbt_translator,
    )

    if op_tags and DAGSTER_DBT_SELECT_METADATA_KEY in op_tags:
        raise DagsterInvalidDefinitionError(
            "To specify a dbt selection, use the 'select' argument, not "
            f"'{DAGSTER_DBT_SELECT_METADATA_KEY}' with op_tags"
        )

    if op_tags and DAGSTER_DBT_EXCLUDE_METADATA_KEY in op_tags:
        raise DagsterInvalidDefinitionError(
            "To specify a dbt exclusion, use the 'exclude' argument, not "
            f"'{DAGSTER_DBT_EXCLUDE_METADATA_KEY}' with op_tags"
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
