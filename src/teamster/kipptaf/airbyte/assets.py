from itertools import chain

from dagster import (
    AssetExecutionContext,
    AssetKey,
    AssetOut,
    AssetsDefinition,
    DagsterInvalidDefinitionError,
    FreshnessPolicy,
    Mapping,
    MetadataValue,
    Optional,
    Output,
    Sequence,
    Set,
    SourceAsset,
    TableSchema,
)
from dagster import _check as check
from dagster import config_from_files, multi_asset
from dagster._core.definitions.events import CoercibleToAssetKey

from .. import CODE_LOCATION


def build_airbyte_cloud_assets(
    connection_id: str,
    destination_tables: Sequence[str],
    asset_key_prefix: Sequence[str] = None,
    group_name: Optional[str] = None,
    normalization_tables: Mapping[str, Set[str]] = None,
    deps: Sequence[CoercibleToAssetKey | AssetsDefinition | SourceAsset] = None,
    upstream_assets: Set[AssetKey] = None,
    schema_by_table_name: Mapping[str, TableSchema] = None,
    freshness_policy: Optional[FreshnessPolicy] = None,
) -> Sequence[AssetsDefinition]:
    if upstream_assets is not None and deps is not None:
        raise DagsterInvalidDefinitionError(
            "Cannot specify both deps and upstream_assets to build_airbyte_assets. "
            "Use only deps instead."
        )

    asset_key_prefix = check.opt_sequence_param(
        asset_key_prefix, "asset_key_prefix", of_type=str
    )

    # Generate a list of outputs, the set of destination tables plus any affiliated
    # normalization tables
    tables = chain.from_iterable(
        chain(
            [destination_tables],
            normalization_tables.values() if normalization_tables else [],
        )
    )

    outputs = {
        table: AssetOut(
            key=AssetKey([*asset_key_prefix, table]),
            metadata={
                "connection_id": connection_id,
                "table_schema": (
                    MetadataValue.table_schema(schema_by_table_name[table])
                    if schema_by_table_name
                    else None
                ),
            },
            freshness_policy=freshness_policy,
            is_required=False,
        )
        for table in tables
    }

    internal_deps = {}

    # If normalization tables are specified, we need to add a dependency from the
    # destination table to the affilitated normalization table
    if normalization_tables:
        for base_table, derived_tables in normalization_tables.items():
            for derived_table in derived_tables:
                internal_deps[derived_table] = {
                    AssetKey([*asset_key_prefix, base_table])
                }

    upstream_deps = deps
    if upstream_assets is not None:
        upstream_deps = list(upstream_assets)

    # All non-normalization tables depend on any user-provided upstream assets
    for table in destination_tables:
        internal_deps[table] = set(upstream_deps) if upstream_deps else set()

    @multi_asset(
        name=f"airbyte_sync_{connection_id[:5]}",
        deps=upstream_deps,
        outs=outputs,
        internal_asset_deps=internal_deps,
        compute_kind="airbyte",
        group_name=group_name,
        can_subset=True,
    )
    def _assets(context: AssetExecutionContext):
        # No connection details (e.g. using Airbyte Cloud) means we just assume
        # that the outputs were produced
        for table_name in context.selected_output_names:
            yield Output(value=None, output_name=table_name)
            if normalization_tables:
                for dependent_table in normalization_tables.get(table_name, set()):
                    yield Output(value=None, output_name=dependent_table)

    return [_assets]


__all__ = []

for a in config_from_files(
    [f"src/teamster/{CODE_LOCATION}/airbyte/config/assets.yaml"]
)["assets"]:
    __all__.extend(
        build_airbyte_cloud_assets(
            **a, asset_key_prefix=[CODE_LOCATION, a["group_name"]]
        )
    )
