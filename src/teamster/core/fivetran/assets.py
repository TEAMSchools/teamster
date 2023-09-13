from typing import Any, Iterator, Mapping, Optional, Sequence

from dagster import (
    AssetKey,
    AssetMaterialization,
    AssetOut,
    AssetsDefinition,
    Nothing,
    OpExecutionContext,
    Output,
    ResourceDefinition,
)
from dagster import _check as check
from dagster import multi_asset
from dagster._core.definitions.metadata import MetadataUserInput


def generate_materializations(
    tracked_asset_keys: list[AssetKey],
) -> Iterator[AssetMaterialization]:
    for asset_key in tracked_asset_keys:
        yield AssetMaterialization(
            asset_key=asset_key, description="Table generated via Fivetran sync"
        )


def build_fivetran_assets(
    connector_id: str,
    destination_tables: Sequence[str],
    io_manager_key: Optional[str] = None,
    asset_key_prefix: Optional[Sequence[str]] = None,
    metadata_by_table_name: Optional[Mapping[str, MetadataUserInput]] = None,
    table_to_asset_key_map: Optional[Mapping[str, AssetKey]] = None,
    resource_defs: Optional[Mapping[str, ResourceDefinition]] = None,
    group_name: Optional[str] = None,
    op_tags: Optional[Mapping[str, Any]] = None,
) -> Sequence[AssetsDefinition]:
    asset_key_prefix = check.opt_sequence_param(
        asset_key_prefix, "asset_key_prefix", of_type=str
    )

    tracked_asset_keys = {
        table: AssetKey([*asset_key_prefix, *table.split(".")])
        for table in destination_tables
    }

    user_facing_asset_keys = table_to_asset_key_map or tracked_asset_keys

    _metadata_by_table_name = check.opt_mapping_param(
        metadata_by_table_name, "metadata_by_table_name", key_type=str
    )

    @multi_asset(
        name=f"fivetran_sync_{connector_id}",
        outs={
            "_".join(key.path): AssetOut(
                key=user_facing_asset_keys[table],
                dagster_type=Nothing,
                io_manager_key=io_manager_key,
                metadata=_metadata_by_table_name.get(table),
            )
            for table, key in tracked_asset_keys.items()
        },
        compute_kind="fivetran",
        resource_defs=resource_defs,
        group_name=group_name,
        op_tags=op_tags,
        can_subset=True,
    )
    def _assets(context: OpExecutionContext) -> Any:
        # materialized_asset_keys = set()
        for materialization in generate_materializations(context.selected_asset_keys):
            # scan through all tables actually created,
            # if it was expected then emit an Output.
            # otherwise, emit a runtime AssetMaterialization
            if materialization.asset_key in tracked_asset_keys.values():
                yield Output(
                    value=None,
                    output_name="_".join(materialization.asset_key.path),
                    metadata=materialization.metadata,
                )
                # materialized_asset_keys.add(materialization.asset_key)
            # else:
            #     yield materialization

    return [_assets]
