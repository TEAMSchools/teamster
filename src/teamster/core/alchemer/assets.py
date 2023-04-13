import pendulum
from alchemer import AlchemerSession
from dagster import (
    AssetOut,
    DynamicPartitionsDefinition,
    OpExecutionContext,
    Output,
    ResourceParam,
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
        },
        partitions_def=DynamicPartitionsDefinition(
            name=f"{code_location}_alchemer_survey_id"
        ),
        op_tags=op_tags,
    )
    def survey_assets(
        context: OpExecutionContext, alchemer: ResourceParam[AlchemerSession]
    ):
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
        name="survey_response_disqualified",
        key_prefix=[code_location, "alchemer"],
        io_manager_key="gcs_avro_io",
        partitions_def=DynamicPartitionsDefinition(
            name=f"{code_location}_alchemer_survey_id"
        ),
        op_tags=op_tags,
    )
    def survey_response_disqualified(
        context: OpExecutionContext, alchemer: ResourceParam[AlchemerSession]
    ):
        survey = alchemer.survey.get(id=context.partition_key)

        data = survey.response.filter("status", "=", "Disqualified").list(
            resultsperpage=500
        )

        schema = get_avro_record_schema(
            name="survey_response", fields=ENDPOINT_FIELDS["survey_response"]
        )

        yield Output(value=(data, schema), metadata={"record_count": len(data)})

    @asset(
        name="survey_response",
        key_prefix=[code_location, "alchemer"],
        io_manager_key="gcs_avro_io",
        partitions_def=DynamicPartitionsDefinition(
            name=f"{code_location}_alchemer_survey_response"
        ),
        op_tags=op_tags,
        output_required=False,
    )
    def survey_response(
        context: OpExecutionContext, alchemer: ResourceParam[AlchemerSession]
    ):
        partition_key_split = context.partition_key.split("_")
        date_submitted = pendulum.from_timestamp(
            int(partition_key_split[1])
        ).to_datetime_string()

        survey = alchemer.survey.get(id=partition_key_split[0])

        data = survey.response.filter("date_submitted", ">=", date_submitted).list(
            resultsperpage=500
        )

        schema = get_avro_record_schema(
            name="survey_response", fields=ENDPOINT_FIELDS["survey_response"]
        )

        yield Output(
            value=(data, schema),
            metadata={"record_count": len(data)},
        )

    return survey_assets, survey_response_disqualified, survey_response
