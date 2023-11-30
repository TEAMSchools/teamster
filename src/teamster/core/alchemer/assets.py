import time

import pendulum
from dagster import DynamicPartitionsDefinition, OpExecutionContext, Output, asset
from requests.exceptions import HTTPError

from teamster.core.alchemer.resources import AlchemerResource
from teamster.core.alchemer.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema

# partitions_def_name = f"{code_location}_alchemer_survey_id"
# DynamicPartitionsDefinition(name=partitions_def_name)


def build_partition_assets(
    partitions_def: DynamicPartitionsDefinition, op_tags={}
) -> list:
    io_manager_key = "io_manager_gcs_avro"
    key_prefix = ["alchemer"]
    group_name = "alchemer"

    @asset(
        name="survey",
        key_prefix=key_prefix,
        io_manager_key=io_manager_key,
        partitions_def=partitions_def,
        op_tags=op_tags,
        group_name=group_name,
    )
    def survey(context: OpExecutionContext, alchemer: AlchemerResource):
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
        partitions_def=partitions_def,
        op_tags=op_tags,
        group_name=group_name,
    )
    def survey_question(context: OpExecutionContext, alchemer: AlchemerResource):
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
        partitions_def=partitions_def,
        op_tags=op_tags,
        group_name=group_name,
    )
    def survey_campaign(context: OpExecutionContext, alchemer: AlchemerResource):
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
            name=partitions_def.name.replace("_id", "_response")
        ),
        op_tags=op_tags,
        group_name=group_name,
    )
    def survey_response(context: OpExecutionContext, alchemer: AlchemerResource):
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
            cursor_timestamp, tz="America/New_York"
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
