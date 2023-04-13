from alchemer import AlchemerSession
from dagster import (
    AssetOut,
    DynamicPartitionsDefinition,
    MultiPartitionsDefinition,
    OpExecutionContext,
    Output,
    Resource,
    asset,
    multi_asset,
)

from teamster.core.alchemer.schema import ENDPOINT_FIELDS
from teamster.core.utils.functions import get_avro_record_schema


def build_partition_assets(code_location, op_tags={}) -> list:
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
            "survey_response_disqualified": AssetOut(
                key_prefix=[code_location, "alchemer"],
                io_manager_key="gcs_avro_io",
            ),
        },
        partitions_def=DynamicPartitionsDefinition(name="survey_id"),
        op_tags=op_tags,
    )
    def _multi_asset(context: OpExecutionContext, alchemer: Resource[AlchemerSession]):
        survey = alchemer.survey.get(id=context.partition_key)

        yield Output(
            output_name="survey",
            value=(
                [survey.data],
                get_avro_record_schema(name="survey", fields=ENDPOINT_FIELDS["survey"]),
            ),
            metadata={"record_count": 1},
        )

        subobjects = {
            "survey_question": survey.question,
            "survey_campaign": survey.campaign,
            "survey_response_disqualified": survey.response.filter(
                "status", "=", "Disqualified"
            ),
        }

        for name, obj in subobjects.items():
            data = obj.list(resultsperpage=500)
            schema = get_avro_record_schema(name=name, fields=ENDPOINT_FIELDS[name])

            yield Output(
                output_name=name,
                value=(data, schema),
                metadata={"record_count": len(data)},
            )

    @asset(
        name="survey_response",
        key_prefix=[code_location, "alchemer"],
        io_manager_key="gcs_avro_io",
        partitions_def=MultiPartitionsDefinition(
            partitions_defs={
                "survey_id": DynamicPartitionsDefinition(name="survey_id"),
                "date_submitted": DynamicPartitionsDefinition(name="date_submitted"),
            }
        ),
        op_tags=op_tags,
    )
    def survey_response(
        context: OpExecutionContext, alchemer: Resource[AlchemerSession]
    ):
        survey_id = context.partition_key.keys_by_dimension["survey_id"]
        date_submitted = (context.partition_key.keys_by_dimension["date_submitted"],)

        survey = alchemer.survey.get(id=survey_id)

        survey_response = survey.response.filter(
            "date_submitted", ">=", date_submitted
        ).list(resultsperpage=500)

        yield Output(
            value=survey_response, metadata={"record_count": len(survey_response)}
        )

    return [_multi_asset, survey_response]
