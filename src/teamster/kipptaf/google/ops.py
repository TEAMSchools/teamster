from teamster.core.google.ops import build_asset_observation_op

from .. import CODE_LOCATION

asset_observation_op = build_asset_observation_op(code_location=CODE_LOCATION)

__all__ = [
    asset_observation_op,
]
