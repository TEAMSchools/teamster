# forked from dagster_fivetran/asset_defs.py
import pickle
from functools import partial
from typing import Callable, List, Optional, Sequence, Union

from dagster import AssetKey
from dagster import _check as check
from dagster._annotations import experimental
from dagster._core.definitions.cacheable_assets import (
    AssetsDefinitionCacheableData,
    CacheableAssetsDefinition,
)
from dagster._core.definitions.events import CoercibleToAssetKeyPrefix
from dagster._core.definitions.resource_definition import ResourceDefinition
from dagster_fivetran.asset_defs import (
    FivetranConnectionMetadata,
    FivetranInstanceCacheableAssetsDefinition,
    _clean_name,
)
from dagster_fivetran.resources import FivetranResource


class FivetranInstanceCacheableAssetsDefinition(
    FivetranInstanceCacheableAssetsDefinition
):
    def __init__(
        self,
        fivetran_resource_def: FivetranResource | ResourceDefinition,
        key_prefix: Sequence[str],
        connector_to_group_fn: Callable[[str], str | None] | None,
        connector_filter: Callable[[FivetranConnectionMetadata], bool] | None,
        connector_to_io_manager_key_fn: Callable[[str], str | None] | None,
        connector_to_asset_key_fn: Callable[[FivetranConnectionMetadata, str], AssetKey]
        | None,
        connector_files,
    ):
        super().__init__(
            fivetran_resource_def,
            key_prefix,
            connector_to_group_fn,
            connector_filter,
            connector_to_io_manager_key_fn,
            connector_to_asset_key_fn,
        )

        self._connector_files = connector_files

    def _get_connectors(self) -> Sequence[FivetranConnectionMetadata]:
        connectors = []

        for connector_file in self._connector_files:
            with open(file=connector_file, mode="rb") as file:
                connectors.append(pickle.load(file=file))

        return connectors

    def compute_cacheable_data(self) -> Sequence[AssetsDefinitionCacheableData]:
        asset_defn_data: List[AssetsDefinitionCacheableData] = []
        for connector in self._get_connectors():
            if not self._connection_filter or self._connection_filter(connector):
                table_to_asset_key = partial(self._connector_to_asset_key_fn, connector)
                asset_defn_data.append(
                    connector.build_asset_defn_metadata(
                        key_prefix=self._key_prefix,
                        group_name=self._connector_to_group_fn(connector.name)
                        if self._connector_to_group_fn
                        else None,
                        io_manager_key=self._connector_to_io_manager_key_fn(
                            connector.name
                        )
                        if self._connector_to_io_manager_key_fn
                        else None,
                        table_to_asset_key_fn=table_to_asset_key,
                    )
                )

        return asset_defn_data


@experimental
def load_assets_from_fivetran_instance(
    fivetran: Union[FivetranResource, ResourceDefinition],
    connector_files,
    key_prefix: Optional[CoercibleToAssetKeyPrefix] = None,
    connector_to_group_fn: Optional[Callable[[str], Optional[str]]] = _clean_name,
    io_manager_key: Optional[str] = None,
    connector_to_io_manager_key_fn: Optional[Callable[[str], Optional[str]]] = None,
    connector_filter: Optional[Callable[[FivetranConnectionMetadata], bool]] = None,
    connector_to_asset_key_fn: Optional[
        Callable[[FivetranConnectionMetadata, str], AssetKey]
    ] = None,
) -> CacheableAssetsDefinition:
    if isinstance(key_prefix, str):
        key_prefix = [key_prefix]
    key_prefix = check.list_param(key_prefix or [], "key_prefix", of_type=str)

    check.invariant(
        not io_manager_key or not connector_to_io_manager_key_fn,
        "Cannot specify both io_manager_key and connector_to_io_manager_key_fn",
    )

    if not connector_to_io_manager_key_fn:

        def connector_to_io_manager_key_fn(_):
            return io_manager_key

    return FivetranInstanceCacheableAssetsDefinition(
        fivetran_resource_def=fivetran,
        key_prefix=key_prefix,
        connector_to_group_fn=connector_to_group_fn,
        connector_to_io_manager_key_fn=connector_to_io_manager_key_fn,
        connector_filter=connector_filter,
        connector_to_asset_key_fn=connector_to_asset_key_fn,
        connector_files=connector_files,
    )
