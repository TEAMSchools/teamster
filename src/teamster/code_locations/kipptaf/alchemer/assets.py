import time

import pendulum
from dagster import DynamicPartitionsDefinition, OpExecutionContext, Output, asset
from requests.exceptions import HTTPError

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.alchemer.schema import (
    SURVEY_CAMPAIGN_SCHEMA,
    SURVEY_QUESTION_SCHEMA,
    SURVEY_RESPONSE_SCHEMA,
    SURVEY_SCHEMA,
)
from teamster.libraries.alchemer.resources import AlchemerResource
from teamster.libraries.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)

key_prefix = [CODE_LOCATION, "alchemer"]

partitions_def = DynamicPartitionsDefinition(name=f"{CODE_LOCATION}_alchemer_survey_id")


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

    yield Output(value=(data, SURVEY_SCHEMA), metadata={"record_count": 1})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=SURVEY_SCHEMA
    )


@asset(
    key=[*key_prefix, "survey_question"],
    check_specs=[build_check_spec_avro_schema_valid([*key_prefix, "survey_question"])],
    partitions_def=partitions_def,
    io_manager_key="io_manager_gcs_avro",
    group_name="alchemer",
    compute_kind="python",
)
def survey_question(context: OpExecutionContext, alchemer: AlchemerResource):
    survey = alchemer._client.survey.get(id=context.partition_key)

    data = survey.question.list(params={"resultsperpage": 500})

    yield Output(
        value=(data, SURVEY_QUESTION_SCHEMA), metadata={"record_count": len(data)}
    )

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=SURVEY_QUESTION_SCHEMA
    )


@asset(
    key=[*key_prefix, "survey_campaign"],
    check_specs=[build_check_spec_avro_schema_valid([*key_prefix, "survey_campaign"])],
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
        value=(data, SURVEY_CAMPAIGN_SCHEMA), metadata={"record_count": len(data)}
    )

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=SURVEY_CAMPAIGN_SCHEMA
    )


@asset(
    key=[*key_prefix, "survey_response"],
    check_specs=[build_check_spec_avro_schema_valid([*key_prefix, "survey_response"])],
    partitions_def=DynamicPartitionsDefinition(
        name=f"{CODE_LOCATION}_alchemer_survey_response"
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
        value=(data, SURVEY_RESPONSE_SCHEMA), metadata={"record_count": len(data)}
    )

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=SURVEY_RESPONSE_SCHEMA
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
        value=(data, SURVEY_RESPONSE_SCHEMA), metadata={"record_count": len(data)}
    )

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=SURVEY_RESPONSE_SCHEMA
    )


survey_metadata_assets = [survey, survey_campaign, survey_question]

assets = [
    survey,
    survey_question,
    survey_campaign,
    survey_response,
    survey_response_disqualified,
]
