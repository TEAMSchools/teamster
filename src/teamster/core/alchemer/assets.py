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

        data = survey.question.list(params={"resultsperpage": 500})
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

        data = survey.campaign.list(params={"resultsperpage": 500})
        schema = get_avro_record_schema(
            name="survey_campaign", fields=ENDPOINT_FIELDS["survey_campaign"]
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
    )
    def survey_response(
        context: OpExecutionContext, alchemer: ResourceParam[AlchemerSession]
    ):
        partition_key_split = context.partition_key.split("_")

        survey = alchemer.survey.get(id=partition_key_split[0])
        date_submitted = pendulum.from_timestamp(
            float(partition_key_split[1]), tz="US/Eastern"
        ).to_datetime_string()

        if date_submitted == pendulum.from_timestamp(0, tz="US/Eastern"):
            data = survey.response.list(params={"resultsperpage": 500})
        else:
            data = survey.response.filter("date_submitted", ">=", date_submitted).list(
                params={"resultsperpage": 500}
            )

        schema = get_avro_record_schema(
            name="survey_response", fields=ENDPOINT_FIELDS["survey_response"]
        )

        yield Output(
            value=(data, schema),
            metadata={"record_count": len(data)},
        )

    return survey, survey_question, survey_campaign, survey_response
