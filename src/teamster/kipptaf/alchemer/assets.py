from teamster.core.alchemer.assets import build_partition_assets
from teamster.kipptaf import CODE_LOCATION

partition_assets = build_partition_assets(code_location=CODE_LOCATION)

__all__ = [
    *partition_assets,
]
