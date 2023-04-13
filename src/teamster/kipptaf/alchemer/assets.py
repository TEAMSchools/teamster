from teamster.core.alchemer.assets import build_partition_assets
from teamster.kipptaf import CODE_LOCATION

survey_assets, survey_response, survey_response_disqualified = build_partition_assets(
    code_location=CODE_LOCATION
)

__all__ = [
    survey_assets,
    survey_response,
    survey_response_disqualified,
]
