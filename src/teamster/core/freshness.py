from collections.abc import Iterable, Sequence

from dagster import AssetKey, AssetsDefinition, AssetSpec, FreshnessPolicy
from dagster._core.definitions.assets.definition.cacheable_assets_definition import (
    CacheableAssetsDefinition,
)
from dagster._core.definitions.source_asset import SourceAsset

LoadedAsset = AssetsDefinition | SourceAsset | CacheableAssetsDefinition | AssetSpec


def apply_freshness_policies(
    assets: Iterable[LoadedAsset],
    policies: dict[AssetKey, FreshnessPolicy],
) -> Sequence[LoadedAsset]:
    def _apply(spec: AssetSpec) -> AssetSpec:
        policy = policies.get(spec.key)
        if policy is None:
            return spec
        return spec.replace_attributes(freshness_policy=policy)

    return [
        asset.map_asset_specs(_apply) if isinstance(asset, AssetsDefinition) else asset
        for asset in assets
    ]
