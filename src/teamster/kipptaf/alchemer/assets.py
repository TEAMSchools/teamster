from teamster.core.alchemer.assets import build_static_partition_assets
from teamster.kipptaf import CODE_LOCATION

static_partition_assets = build_static_partition_assets(code_location=CODE_LOCATION)

__all__ = [
    static_partition_assets,
]
