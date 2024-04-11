import time

import pendulum
from alchemer import AlchemerSession
from dagster import (
    DynamicPartitionsDefinition,
    OpExecutionContext,
    Output,
    ResourceParam,
    asset,
)
from requests.exceptions import HTTPError

from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_schema_valid_check_spec,
)

from .. import CODE_LOCATION
from .schema import (
    SURVEY_CAMPAIGN_SCHEMA,
    SURVEY_QUESTION_SCHEMA,
    SURVEY_RESPONSE_DQ_SCHEMA,
    SURVEY_RESPONSE_SCHEMA,
    SURVEY_SCHEMA,
)

key_prefix = [CODE_LOCATION, "alchemer"]
asset_kwargs = {
    "io_manager_key": "io_manager_gcs_avro",
    "group_name": "alchemer",
    "compute_kind": "alchemer",
}

partitions_def = DynamicPartitionsDefinition(name=f"{CODE_LOCATION}_alchemer_survey_id")


@asset(
    key=[*key_prefix, "survey"],
    check_specs=[get_avro_schema_valid_check_spec([*key_prefix, "survey"])],
    partitions_def=partitions_def,
    **asset_kwargs,  # type: ignore
)
def survey(context: OpExecutionContext, alchemer: ResourceParam[AlchemerSession]):
    survey = alchemer.survey.get(id=context.partition_key)

    data = [survey.data]

    yield Output(value=(data, SURVEY_SCHEMA), metadata={"record_count": 1})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=SURVEY_SCHEMA
    )


@asset(
    key=[*key_prefix, "survey_question"],
    check_specs=[get_avro_schema_valid_check_spec([*key_prefix, "survey_question"])],
    partitions_def=partitions_def,
    **asset_kwargs,  # type: ignore
)
def survey_question(
    context: OpExecutionContext, alchemer: ResourceParam[AlchemerSession]
):
    survey = alchemer.survey.get(id=context.partition_key)

    data = survey.question.list(params={"resultsperpage": 500})

    yield Output(
        value=(data, SURVEY_QUESTION_SCHEMA), metadata={"record_count": len(data)}
    )

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=SURVEY_QUESTION_SCHEMA
    )


@asset(
    key=[*key_prefix, "survey_campaign"],
    check_specs=[get_avro_schema_valid_check_spec([*key_prefix, "survey_campaign"])],
    partitions_def=partitions_def,
    **asset_kwargs,  # type: ignore
)
def survey_campaign(
    context: OpExecutionContext, alchemer: ResourceParam[AlchemerSession]
):
    asset_name = context.assets_def.key[-1]
    context.log.debug(asset_name)

    survey = alchemer.survey.get(id=context.partition_key)

    data = survey.campaign.list(params={"resultsperpage": 500})

    yield Output(
        value=(data, SURVEY_CAMPAIGN_SCHEMA), metadata={"record_count": len(data)}
    )

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=SURVEY_CAMPAIGN_SCHEMA
    )


@asset(
    key=[*key_prefix, "survey_response"],
    check_specs=[get_avro_schema_valid_check_spec([*key_prefix, "survey_response"])],
    partitions_def=DynamicPartitionsDefinition(
        name=f"{CODE_LOCATION}_alchemer_survey_response"
    ),
    **asset_kwargs,  # type: ignore
)
def survey_response(
    context: OpExecutionContext, alchemer: ResourceParam[AlchemerSession]
):
    partition_key_split = context.partition_key.split("_")

    try:
        survey = alchemer.survey.get(id=partition_key_split[0])
    except HTTPError as e:
        context.log.exception(e)
        context.log.info("Retrying in 60 seconds")
        time.sleep(60)

        survey = alchemer.survey.get(id=partition_key_split[0])

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
        get_avro_schema_valid_check_spec([*key_prefix, "survey_response_disqualified"])
    ],
    partitions_def=partitions_def,
    **asset_kwargs,  # type: ignore
)
def survey_response_disqualified(
    context: OpExecutionContext, alchemer: ResourceParam[AlchemerSession]
):
    try:
        survey = alchemer.survey.get(id=context.partition_key)
    except HTTPError as e:
        context.log.exception(e)
        context.log.info("Retrying in 60 seconds")
        time.sleep(60)

        survey = alchemer.survey.get(id=context.partition_key)

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
        value=(data, SURVEY_RESPONSE_DQ_SCHEMA), metadata={"record_count": len(data)}
    )

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=SURVEY_RESPONSE_DQ_SCHEMA
    )


survey_metadata_assets = [survey, survey_campaign, survey_question]

_all = [
    survey,
    survey_question,
    survey_campaign,
    survey_response,
    survey_response_disqualified,
]
