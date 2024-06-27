from typing import TYPE_CHECKING, Any, Mapping, Sequence

from dagster import AssetDep, AssetKey, DagsterInvalidDefinitionError
from dagster_dbt import DagsterDbtTranslator
from dagster_dbt.asset_utils import (
    DAGSTER_DBT_MANIFEST_METADATA_KEY,
    DAGSTER_DBT_TRANSLATOR_METADATA_KEY,
    DUPLICATE_ASSET_KEY_ERROR_MESSAGE,
    _attach_sql_model_code_reference,
    get_deps,
    has_self_dependency,
)
from dagster_dbt.utils import (
    dagster_name_fn,
    get_dbt_resource_props_by_dbt_unique_id_from_manifest,
    select_unique_ids_from_manifest,
)

if TYPE_CHECKING:
    from dagster_dbt.dagster_dbt_translator import DagsterDbtTranslator
    from dagster_dbt.dbt_project import DbtProject


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


def build_dbt_multi_asset_deps(
    *,
    manifest: Mapping[str, Any],
    dagster_dbt_translator: "DagsterDbtTranslator",
    select: str,
    exclude: str,
    project: "DbtProject | None" = None,
) -> tuple[Sequence[AssetDep], dict[str, set[AssetKey]]]:
    """Forked from dagster_dbt.asset_decorator.build_dbt_multi_asset_args"""
    from dagster_dbt.dagster_dbt_translator import DbtManifestWrapper

    deps: set[AssetDep] = set()
    internal_asset_deps: dict[str, set[AssetKey]] = {}
    dbt_unique_id_and_resource_types_by_asset_key: dict[
        AssetKey, tuple[set[str], set[str]]
    ] = {}

    unique_ids = select_unique_ids_from_manifest(
        select=select, exclude=exclude or "", manifest_json=manifest
    )
    dbt_resource_props_by_dbt_unique_id = (
        get_dbt_resource_props_by_dbt_unique_id_from_manifest(manifest)
    )

    dbt_unique_id_deps = get_deps(
        dbt_nodes=dbt_resource_props_by_dbt_unique_id,
        selected_unique_ids=unique_ids,
        asset_resource_types=["source"],
    )

    for unique_id, parent_unique_ids in dbt_unique_id_deps.items():
        dbt_resource_props = dbt_resource_props_by_dbt_unique_id[unique_id]

        output_name = dagster_name_fn(dbt_resource_props)
        asset_key = dagster_dbt_translator.get_asset_key(dbt_resource_props)

        unique_ids_for_asset_key, resource_types_for_asset_key = (
            dbt_unique_id_and_resource_types_by_asset_key.setdefault(
                asset_key, (set(), set())
            )
        )

        unique_ids_for_asset_key.add(unique_id)
        resource_types_for_asset_key.add(dbt_resource_props["resource_type"])

        metadata = {
            **dagster_dbt_translator.get_metadata(dbt_resource_props),
            DAGSTER_DBT_MANIFEST_METADATA_KEY: DbtManifestWrapper(manifest=manifest),
            DAGSTER_DBT_TRANSLATOR_METADATA_KEY: dagster_dbt_translator,
        }

        if dagster_dbt_translator.settings.enable_code_references:
            if not project:
                raise DagsterInvalidDefinitionError(
                    "enable_code_references requires a DbtProject to be supplied"
                    " to the @dbt_assets decorator."
                )

            metadata = _attach_sql_model_code_reference(
                existing_metadata=metadata,
                dbt_resource_props=dbt_resource_props,
                project=project,
            )

        # Translate parent unique ids to dependencies
        output_internal_deps = internal_asset_deps.setdefault(output_name, set())

        for parent_unique_id in parent_unique_ids:
            dbt_parent_resource_props = dbt_resource_props_by_dbt_unique_id[
                parent_unique_id
            ]

            parent_asset_key = dagster_dbt_translator.get_asset_key(
                dbt_parent_resource_props
            )
            parent_partition_mapping = dagster_dbt_translator.get_partition_mapping(
                dbt_resource_props,
                dbt_parent_resource_props=dbt_parent_resource_props,
            )

            parent_unique_ids_for_asset_key, parent_resource_types_for_asset_key = (
                dbt_unique_id_and_resource_types_by_asset_key.setdefault(
                    parent_asset_key, (set(), set())
                )
            )

            parent_unique_ids_for_asset_key.add(parent_unique_id)
            parent_resource_types_for_asset_key.add(
                dbt_parent_resource_props["resource_type"]
            )

            # Add this parent as an internal dependency
            output_internal_deps.add(parent_asset_key)

            # Mark this parent as an input if it has no dependencies
            if parent_unique_id not in dbt_unique_id_deps:
                deps.add(
                    AssetDep(
                        asset=parent_asset_key,
                        partition_mapping=parent_partition_mapping,
                    )
                )

        self_partition_mapping = dagster_dbt_translator.get_partition_mapping(
            dbt_resource_props,
            dbt_parent_resource_props=dbt_resource_props,
        )

        if self_partition_mapping and has_self_dependency(dbt_resource_props):
            deps.add(
                AssetDep(asset=asset_key, partition_mapping=self_partition_mapping)
            )
            output_internal_deps.add(asset_key)

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
                unique_id_file_path = dbt_resource_props_by_dbt_unique_id[id][
                    "original_file_path"
                ]
                formatted_ids.append(f"  - `{id}` ({unique_id_file_path})")

            error_messages.append(
                "\n".join(
                    [
                        f"The following dbt resources have the asset key `{asset_key.path}`:",
                        *formatted_ids,
                    ]
                )
            )

        raise DagsterInvalidDefinitionError(
            "\n\n".join([DUPLICATE_ASSET_KEY_ERROR_MESSAGE, *error_messages])
        )

    return list(deps), internal_asset_deps
