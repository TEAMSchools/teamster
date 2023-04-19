import pendulum
from alchemer import AlchemerSession
from dagster import (
    DynamicPartitionsDefinition,
    OpExecutionContext,
    Output,
    ResourceParam,
    asset,
)

from teamster.core.alchemer.schema import ENDPOINT_FIELDS
from teamster.core.utils.functions import get_avro_record_schema


def build_partition_assets(code_location, op_tags={}) -> list:
    io_manager_key = "gcs_avro_io"
    key_prefix = [code_location, "alchemer"]
    partitions_def_name = f"{code_location}_alchemer_survey_id"

    @asset(
        name="survey",
        key_prefix=key_prefix,
        io_manager_key=io_manager_key,
        partitions_def=DynamicPartitionsDefinition(name=partitions_def_name),
        op_tags=op_tags,
    )
    def survey(context: OpExecutionContext, alchemer: ResourceParam[AlchemerSession]):
        survey = alchemer.survey.get(id=context.partition_key)

        yield Output(
            value=(
                [survey.data],
                get_avro_record_schema(name="survey", fields=ENDPOINT_FIELDS["survey"]),
            ),
            metadata={"record_count": 1},
        )

    @asset(
        name="survey_question",
        key_prefix=key_prefix,
        io_manager_key=io_manager_key,
        partitions_def=DynamicPartitionsDefinition(name=partitions_def_name),
        op_tags=op_tags,
    )
    def survey_question(
        context: OpExecutionContext, alchemer: ResourceParam[AlchemerSession]
    ):
        survey = alchemer.survey.get(id=context.partition_key)

        data = survey.question.list(resultsperpage=500)
        schema = get_avro_record_schema(
            name="survey_question", fields=ENDPOINT_FIELDS["survey_question"]
        )

        yield Output(value=(data, schema), metadata={"record_count": len(data)})

    @asset(
        name="survey_campaign",
        key_prefix=key_prefix,
        io_manager_key=io_manager_key,
        partitions_def=DynamicPartitionsDefinition(name=partitions_def_name),
        op_tags=op_tags,
    )
    def survey_campaign(
        context: OpExecutionContext, alchemer: ResourceParam[AlchemerSession]
    ):
        asset_name = context.assets_def.key[-1]
        context.log.debug(asset_name)

        survey = alchemer.survey.get(id=context.partition_key)

        data = survey.campaign.list(resultsperpage=500)
        schema = get_avro_record_schema(
            name="survey_campaign", fields=ENDPOINT_FIELDS["survey_campaign"]
        )

        yield Output(value=(data, schema), metadata={"record_count": len(data)})

    @asset(
        name="survey_response_disqualified",
        key_prefix=key_prefix,
        io_manager_key=io_manager_key,
        partitions_def=DynamicPartitionsDefinition(name=partitions_def_name),
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
        key_prefix=key_prefix,
        io_manager_key=io_manager_key,
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

    return (
        survey,
        survey_question,
        survey_campaign,
        survey_response_disqualified,
        survey_response,
    )
