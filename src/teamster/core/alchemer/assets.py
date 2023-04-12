from alchemer import AlchemerSession
from dagster import (
    AssetOut,
    AssetsDefinition,
    DynamicPartitionsDefinition,
    OpExecutionContext,
    Output,
    Resource,
    multi_asset,
)

from teamster.core.alchemer.schema import ENDPOINT_FIELDS
from teamster.core.utils.functions import get_avro_record_schema


def build_static_partition_assets(code_location, op_tags={}) -> AssetsDefinition:
    @multi_asset(
        outs={
            "survey": AssetOut(
                key_prefix=[code_location, "alchemer"],
                io_manager_key="gcs_avro_io",
            ),
            "survey_question": AssetOut(
                key_prefix=[code_location, "alchemer"],
                io_manager_key="gcs_avro_io",
            ),
            "survey_campaign": AssetOut(
                key_prefix=[code_location, "alchemer"],
                io_manager_key="gcs_avro_io",
            ),
        },
        partitions_def=DynamicPartitionsDefinition(name="survey_id"),
        op_tags=op_tags,
    )
    def _multi_asset(context: OpExecutionContext, alchemer: Resource[AlchemerSession]):
        survey = alchemer.survey.get(context.partition_key)

        yield Output(
            output_name="survey",
            value=(
                survey.data,
                get_avro_record_schema(name="survey", fields=ENDPOINT_FIELDS["survey"]),
            ),
            metadata={"record_count": 1},
        )

        survey_question_data = survey.question.list()
        yield Output(
            output_name="survey_question",
            value=(
                survey_question_data,
                get_avro_record_schema(
                    name="survey_question", fields=ENDPOINT_FIELDS["survey_question"]
                ),
            ),
            metadata={"record_count": len(survey_question_data)},
        )

        survey_campaign_data = survey.campaign.list()
        yield Output(
            output_name="survey_campaign",
            value=(
                survey_campaign_data,
                get_avro_record_schema(
                    name="survey_campaign", fields=ENDPOINT_FIELDS["survey_campaign"]
                ),
            ),
            metadata={"record_count": len(survey_campaign_data)},
        )

    return _multi_asset
