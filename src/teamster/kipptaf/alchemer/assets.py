from teamster.core.alchemer.assets import build_partition_assets

from .. import CODE_LOCATION

survey, survey_question, survey_campaign, survey_response = build_partition_assets(
    code_location=CODE_LOCATION
)

survey_metadata_assets = [survey, survey_campaign, survey_question]

__all__ = [
    survey,
    survey_question,
    survey_campaign,
    survey_response,
]
