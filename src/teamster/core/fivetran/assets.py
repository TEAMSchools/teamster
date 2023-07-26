from typing import Any, Mapping, Optional, Sequence

import pendulum
from dagster import (
    AssetKey,
    AssetOut,
    AssetsDefinition,
    DagsterStepOutputNotFoundError,
    DataVersion,
    Nothing,
    OpExecutionContext,
    Output,
    ResourceDefinition,
)
from dagster import _check as check
from dagster import multi_asset, observable_source_asset
from dagster._core.definitions.metadata import MetadataUserInput
from dagster_fivetran import FivetranOutput, FivetranResource
from dagster_fivetran.utils import generate_materializations


def build_fivetran_asset(
    name, code_location, schema_name, connector_id, group_name, **kwargs
):
    @observable_source_asset(
        name=name,
        key_prefix=[code_location, schema_name],
        metadata={"connector_id": connector_id, "schema_name": schema_name},
        group_name=group_name,
        **kwargs,
    )
    def _asset():
        return DataVersion(str(pendulum.now().timestamp()))

    return _asset


def build_fivetran_assets(
    connector_id: str,
    destination_tables: Sequence[str],
    io_manager_key: Optional[str] = None,
    asset_key_prefix: Optional[Sequence[str]] = None,
    metadata_by_table_name: Optional[Mapping[str, MetadataUserInput]] = None,
    table_to_asset_key_map: Optional[Mapping[str, AssetKey]] = None,
    resource_defs: Optional[Mapping[str, ResourceDefinition]] = None,
    group_name: Optional[str] = None,
    infer_missing_tables: bool = False,
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
                io_manager_key=io_manager_key,
                key=user_facing_asset_keys[table],
                metadata=_metadata_by_table_name.get(table),
                dagster_type=Nothing,
            )
            for table, key in tracked_asset_keys.items()
        },
        compute_kind="fivetran",
        resource_defs=resource_defs,
        group_name=group_name,
        op_tags=op_tags,
        can_subset=True,
    )
    def _assets(context: OpExecutionContext, fivetran: FivetranResource) -> Any:
        materialized_asset_keys = set()
        for materialization in generate_materializations(
            fivetran_output=FivetranOutput(
                connector_details=fivetran.get_connector_details(connector_id),
                schema_config={},
            ),
            asset_key_prefix=asset_key_prefix,
        ):
            # scan through all tables actually created, if it was expected then emit an
            # Output. otherwise, emit a runtime AssetMaterialization
            if materialization.asset_key in tracked_asset_keys.values():
                yield Output(
                    value=None,
                    output_name="_".join(materialization.asset_key.path),
                    metadata=materialization.metadata,
                )
                materialized_asset_keys.add(materialization.asset_key)

            else:
                yield materialization

        unmaterialized_asset_keys = (
            set(tracked_asset_keys.values()) - materialized_asset_keys
        )
        if infer_missing_tables:
            for asset_key in unmaterialized_asset_keys:
                yield Output(value=None, output_name="_".join(asset_key.path))

        else:
            if unmaterialized_asset_keys:
                asset_key = list(unmaterialized_asset_keys)[0]
                output_name = "_".join(asset_key.path)
                raise DagsterStepOutputNotFoundError(
                    (
                        f"Core compute for {context.op_def.name} did not return an "
                        f"output for non-optional output '{output_name}'."
                    ),
                    step_key=context.get_step_execution_context().step.key,
                    output_name=output_name,
                )

    return [_assets]
