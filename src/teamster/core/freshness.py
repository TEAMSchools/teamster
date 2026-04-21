from collections.abc import Iterable

from dagster import AssetKey, AssetsDefinition, AssetSpec, FreshnessPolicy, SourceAsset

# CacheableAssetsDefinition has no public import path but appears in
# load_assets_from_modules's return type union, so we keep LoadedAsset
# aligned with that signature for callers.
from dagster._core.definitions.assets.definition.cacheable_assets_definition import (
    CacheableAssetsDefinition,
)

LoadedAsset = AssetsDefinition | SourceAsset | CacheableAssetsDefinition | AssetSpec


def apply_freshness_policies(
    assets: Iterable[LoadedAsset],
    policies: dict[AssetKey, FreshnessPolicy],
) -> list[LoadedAsset]:
    def _apply(spec: AssetSpec) -> AssetSpec:
        policy = policies.get(spec.key)
        if policy is None:
            return spec
        return spec.replace_attributes(freshness_policy=policy)

    result: list[LoadedAsset] = []
    for asset in assets:
        if isinstance(asset, AssetsDefinition):
            result.append(asset.map_asset_specs(_apply))
        elif isinstance(asset, AssetSpec):
            result.append(_apply(asset))
        else:
            result.append(asset)
    return result
