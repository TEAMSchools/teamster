# forked from dagster_fivetran/asset_defs.py
import hashlib
import inspect
import json
from functools import partial
from typing import Callable, List, Optional, Sequence, Union

from dagster import AssetKey, AssetsDefinition
from dagster import _check as check
from dagster._annotations import experimental
from dagster._core.definitions.cacheable_assets import (
    AssetsDefinitionCacheableData,
    CacheableAssetsDefinition,
)
from dagster._core.definitions.events import CoercibleToAssetKeyPrefix
from dagster._core.definitions.resource_definition import ResourceDefinition
from dagster._core.execution.context.init import build_init_resource_context
from dagster_fivetran.asset_defs import (
    FivetranConnectionMetadata,
    _build_fivetran_assets_from_metadata,
    _clean_name,
)
from dagster_fivetran.resources import FivetranResource
from dagster_fivetran.utils import get_fivetran_connector_url


class FivetranInstanceCacheableAssetsDefinition(CacheableAssetsDefinition):
    def __init__(
        self,
        fivetran_resource_def: Union[FivetranResource, ResourceDefinition],
        key_prefix: Sequence[str],
        connector_to_group_fn: Optional[Callable[[str], Optional[str]]],
        connector_filter: Optional[Callable[[FivetranConnectionMetadata], bool]],
        connector_to_io_manager_key_fn: Optional[Callable[[str], Optional[str]]],
        connector_to_asset_key_fn: Optional[
            Callable[[FivetranConnectionMetadata, str], AssetKey]
        ],
        schema_files: list[str] = [],
    ):
        self._fivetran_resource_def = fivetran_resource_def
        self._fivetran_instance: FivetranResource = (
            fivetran_resource_def
            if isinstance(fivetran_resource_def, FivetranResource)
            else fivetran_resource_def(build_init_resource_context())
        )

        self._key_prefix = key_prefix
        self._connector_to_group_fn = connector_to_group_fn
        self._connection_filter = connector_filter
        self._connector_to_io_manager_key_fn = connector_to_io_manager_key_fn
        self._connector_to_asset_key_fn: Callable[
            [FivetranConnectionMetadata, str], AssetKey
        ] = connector_to_asset_key_fn or (
            lambda _, table: AssetKey(path=table.split("."))
        )
        self._schema_files = schema_files

        contents = hashlib.sha1()
        contents.update(",".join(key_prefix).encode("utf-8"))
        if connector_filter:
            contents.update(inspect.getsource(connector_filter).encode("utf-8"))

        super().__init__(unique_id=f"fivetran-{contents.hexdigest()}")

    def _get_connectors(self) -> Sequence[FivetranConnectionMetadata]:
        output_connectors: List[FivetranConnectionMetadata] = []

        groups = self._fivetran_instance.make_request("GET", "groups")["items"]

        for group in groups:
            group_id = group["id"]

            connectors = self._fivetran_instance.make_request(
                "GET", f"groups/{group_id}/connectors"
            )["items"]
            for connector in connectors:
                connector_id = connector["id"]

                connector_name = connector["schema"]
                connector_url = get_fivetran_connector_url(connector)

                connection_metadata = FivetranConnectionMetadata(
                    name=connector_name,
                    connector_id=connector_id,
                    connector_url=connector_url,
                    schemas={},
                )

                if not self._connection_filter(connection_metadata):
                    continue

                setup_state = connector.get("status", {}).get("setup_state")
                if setup_state and setup_state in ("incomplete", "broken"):
                    continue

                schema_file = [s for s in self._schema_files if connector_id in s]

                if schema_file:
                    with open(file=schema_file[0], mode="r") as fp:
                        schemas = json.load(fp=fp)
                else:
                    schemas = self._fivetran_instance.make_request(
                        "GET", f"connectors/{connector_id}/schemas"
                    )

                output_connectors.append(
                    FivetranConnectionMetadata(
                        name=connector_name,
                        connector_id=connector_id,
                        connector_url=connector_url,
                        schemas=schemas,
                    )
                )

        return output_connectors

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

    def build_definitions(
        self, data: Sequence[AssetsDefinitionCacheableData]
    ) -> Sequence[AssetsDefinition]:
        return [
            _build_fivetran_assets_from_metadata(
                meta, {"fivetran": self._fivetran_instance.get_resource_definition()}
            )
            for meta in data
        ]


@experimental
def load_assets_from_fivetran_instance(
    fivetran: Union[FivetranResource, ResourceDefinition],
    key_prefix: Optional[CoercibleToAssetKeyPrefix] = None,
    connector_to_group_fn: Optional[Callable[[str], Optional[str]]] = _clean_name,
    io_manager_key: Optional[str] = None,
    connector_to_io_manager_key_fn: Optional[Callable[[str], Optional[str]]] = None,
    connector_filter: Optional[Callable[[FivetranConnectionMetadata], bool]] = None,
    connector_to_asset_key_fn: Optional[
        Callable[[FivetranConnectionMetadata, str], AssetKey]
    ] = None,
    schema_files: list[str] = [],
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
        schema_files=schema_files,
    )
