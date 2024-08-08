import time

import pendulum
from dagster import DynamicPartitionsDefinition, OpExecutionContext, Output, asset
from requests.exceptions import HTTPError

from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.alchemer.resources import AlchemerResource


def build_alchemer_assets(
    code_location,
    survey_schema,
    survey_question_schema,
    survey_campaign_schema,
    survey_response_schema,
):
    key_prefix = [code_location, "alchemer"]

    partitions_def = DynamicPartitionsDefinition(
        name=f"{code_location}_alchemer_survey_id"
    )

    @asset(
        key=[*key_prefix, "survey"],
        check_specs=[build_check_spec_avro_schema_valid([*key_prefix, "survey"])],
        partitions_def=partitions_def,
        io_manager_key="io_manager_gcs_avro",
        group_name="alchemer",
        compute_kind="python",
    )
    def survey(context: OpExecutionContext, alchemer: AlchemerResource):
        survey = alchemer._client.survey.get(id=context.partition_key)

        data = [survey.data]

        yield Output(value=(data, survey_schema), metadata={"record_count": 1})

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=survey_schema
        )

    @asset(
        key=[*key_prefix, "survey_question"],
        check_specs=[
            build_check_spec_avro_schema_valid([*key_prefix, "survey_question"])
        ],
        partitions_def=partitions_def,
        io_manager_key="io_manager_gcs_avro",
        group_name="alchemer",
        compute_kind="python",
    )
    def survey_question(context: OpExecutionContext, alchemer: AlchemerResource):
        survey = alchemer._client.survey.get(id=context.partition_key)

        data = survey.question.list(params={"resultsperpage": 500})

        yield Output(
            value=(data, survey_question_schema), metadata={"record_count": len(data)}
        )

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=survey_question_schema
        )

    @asset(
        key=[*key_prefix, "survey_campaign"],
        check_specs=[
            build_check_spec_avro_schema_valid([*key_prefix, "survey_campaign"])
        ],
        partitions_def=partitions_def,
        io_manager_key="io_manager_gcs_avro",
        group_name="alchemer",
        compute_kind="python",
    )
    def survey_campaign(context: OpExecutionContext, alchemer: AlchemerResource):
        asset_name = context.assets_def.key[-1]
        context.log.debug(asset_name)

        survey = alchemer._client.survey.get(id=context.partition_key)

        data = survey.campaign.list(params={"resultsperpage": 500})

        yield Output(
            value=(data, survey_campaign_schema), metadata={"record_count": len(data)}
        )

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=survey_campaign_schema
        )

    @asset(
        key=[*key_prefix, "survey_response"],
        check_specs=[
            build_check_spec_avro_schema_valid([*key_prefix, "survey_response"])
        ],
        partitions_def=DynamicPartitionsDefinition(
            name=f"{code_location}_alchemer_survey_response"
        ),
        io_manager_key="io_manager_gcs_avro",
        group_name="alchemer",
        compute_kind="python",
    )
    def survey_response(context: OpExecutionContext, alchemer: AlchemerResource):
        partition_key_split = context.partition_key.split("_")

        try:
            survey = alchemer._client.survey.get(id=partition_key_split[0])
        except HTTPError as e:
            context.log.exception(e)
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
            context.log.exception(e)
            context.log.info("Retrying in 60 seconds")
            time.sleep(60)

            # resultsperpage can produce a 500 error
            data = survey_response_obj.list()

        yield Output(
            value=(data, survey_response_schema), metadata={"record_count": len(data)}
        )

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=survey_response_schema
        )

    @asset(
        key=[*key_prefix, "survey_response_disqualified"],
        check_specs=[
            build_check_spec_avro_schema_valid(
                [*key_prefix, "survey_response_disqualified"]
            )
        ],
        partitions_def=partitions_def,
        io_manager_key="io_manager_gcs_avro",
        group_name="alchemer",
        compute_kind="python",
    )
    def survey_response_disqualified(
        context: OpExecutionContext, alchemer: AlchemerResource
    ):
        try:
            survey = alchemer._client.survey.get(id=context.partition_key)
        except HTTPError as e:
            context.log.exception(e)
            context.log.info("Retrying in 60 seconds")
            time.sleep(60)

            survey = alchemer._client.survey.get(id=context.partition_key)

        survey_response_obj = survey.response.filter("status", "=", "DISQUALIFIED")

        try:
            data = survey_response_obj.list(params={"resultsperpage": 500})
        except HTTPError as e:
            context.log.exception(e)
            context.log.info("Retrying in 60 seconds")
            time.sleep(60)

            # resultsperpage can produce a 500 error
            data = survey_response_obj.list()

        yield Output(
            value=(data, survey_response_schema), metadata={"record_count": len(data)}
        )

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=survey_response_schema
        )

    return (
        survey,
        survey_campaign,
        survey_question,
        survey_response,
        survey_response_disqualified,
    )
