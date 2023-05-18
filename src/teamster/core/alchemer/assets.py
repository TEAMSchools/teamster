import time

import pendulum
from dagster import (
    DynamicPartitionsDefinition,
    OpExecutionContext,
    Output,
    ResourceParam,
    asset,
)
from requests.exceptions import HTTPError

from teamster.core.alchemer.resources import AlchemerResource
from teamster.core.alchemer.schema import ASSET_FIELDS
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
    def survey(context: OpExecutionContext, alchemer: ResourceParam[AlchemerResource]):
        survey = alchemer._client.survey.get(id=context.partition_key)

        yield Output(
            value=(
                [survey.data],
                get_avro_record_schema(name="survey", fields=ASSET_FIELDS["survey"]),
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
        context: OpExecutionContext, alchemer: ResourceParam[AlchemerResource]
    ):
        survey = alchemer._client.survey.get(id=context.partition_key)

        data = survey.question.list(params={"resultsperpage": 500})
        schema = get_avro_record_schema(
            name="survey_question", fields=ASSET_FIELDS["survey_question"]
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
        context: OpExecutionContext, alchemer: ResourceParam[AlchemerResource]
    ):
        asset_name = context.assets_def.key[-1]
        context.log.debug(asset_name)

        survey = alchemer._client.survey.get(id=context.partition_key)

        data = survey.campaign.list(params={"resultsperpage": 500})
        schema = get_avro_record_schema(
            name="survey_campaign", fields=ASSET_FIELDS["survey_campaign"]
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
        context: OpExecutionContext, alchemer: ResourceParam[AlchemerResource]
    ):
        partition_key_split = context.partition_key.split("_")

        try:
            survey = alchemer._client.survey.get(id=partition_key_split[0])
        except HTTPError as e:
            context.log.error(e)
            context.log.info("Retrying in 60 seconds")
            time.sleep(60)

            survey = alchemer._client.survey.get(id=partition_key_split[0])

        cursor_timestamp = float(partition_key_split[1])

        date_submitted = pendulum.from_timestamp(
            cursor_timestamp, tz="US/Eastern"
        ).to_datetime_string()

        if cursor_timestamp == 0:
            survey_response_obj = survey.response
        else:
            survey_response_obj = survey.response.filter(
                "date_submitted", ">=", date_submitted
            )

        try:
            data = survey_response_obj.list(params={"resultsperpage": 500})
        except HTTPError as e:
            context.log.error(e)
            context.log.info("Retrying in 60 seconds")
            time.sleep(60)

            # resultsperpage can produce a 500 error
            data = survey_response_obj.list()

        schema = get_avro_record_schema(
            name="survey_response", fields=ASSET_FIELDS["survey_response"]
        )

        yield Output(
            value=(data, schema),
            metadata={"record_count": len(data)},
        )

    return survey, survey_question, survey_campaign, survey_response
