from dagster import config_from_files

from teamster.core.schoolmint.grow.assets import (
    build_multi_partition_asset,
    build_static_partition_asset,
)

from .. import CODE_LOCATION, LOCAL_TIMEZONE

config_dir = f"src/teamster/{CODE_LOCATION}/schoolmint/config"


static_partition_assets = [
    build_static_partition_asset(code_location=CODE_LOCATION, **endpoint)
    for endpoint in config_from_files([f"{config_dir}/static-partition-assets.yaml"])[
        "endpoints"
    ]
]

multi_partition_assets = [
    build_multi_partition_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE.name, **endpoint
    )
    for endpoint in config_from_files([f"{config_dir}/multi-partition-assets.yaml"])[
        "endpoints"
    ]
]

__all__ = [
    *static_partition_assets,
    *multi_partition_assets,
]
