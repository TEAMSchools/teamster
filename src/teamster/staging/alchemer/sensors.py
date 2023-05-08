from teamster.core.alchemer.sensors import (
    build_survey_metadata_asset_sensor,
    build_survey_response_asset_sensor,
)

from .. import CODE_LOCATION
from .assets import survey_metadata_assets, survey_response

survey_metadata_asset_sensor = build_survey_metadata_asset_sensor(
    code_location=CODE_LOCATION, asset_defs=survey_metadata_assets
)

survey_response_asset_sensor = build_survey_response_asset_sensor(
    code_location=CODE_LOCATION, asset_def=survey_response, minimum_interval_seconds=600
)

__all__ = [
    survey_metadata_asset_sensor,
    survey_response_asset_sensor,
]
