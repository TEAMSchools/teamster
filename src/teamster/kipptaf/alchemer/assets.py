import json
import pathlib
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
    get_avro_record_schema,
    get_avro_schema_valid_check_spec,
)

from .. import CODE_LOCATION
from .schema import (
    SURVEY_CAMPAIGN_FIELDS,
    SURVEY_FIELDS,
    SURVEY_RESPONSE_FIELDS,
    get_survey_question_fields,
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

    data_str = json.dumps(obj=survey.data).replace("soft-required", "soft_required")

    data = [json.loads(s=data_str)]
    schema = get_avro_record_schema(name="survey", fields=SURVEY_FIELDS)

    fp = pathlib.Path("env/alchemer/survey.json")
    fp.parent.mkdir(parents=True, exist_ok=True)
    json.dump(obj=data, fp=fp.open(mode="w"))

    yield Output(value=(data, schema), metadata={"record_count": 1})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=schema
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

    data_str = json.dumps(obj=data).replace("soft-required", "soft_required")

    data = json.loads(s=data_str)
    schema = get_avro_record_schema(
        name="survey_question",
        fields=get_survey_question_fields(namespace="surveyquestion", depth=2),
    )

    fp = pathlib.Path("env/alchemer/survey_question.json")
    fp.parent.mkdir(parents=True, exist_ok=True)
    json.dump(obj=data, fp=fp.open(mode="w"))

    yield Output(value=(data, schema), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=schema
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
    schema = get_avro_record_schema(
        name="survey_campaign", fields=SURVEY_CAMPAIGN_FIELDS
    )

    fp = pathlib.Path("env/alchemer/survey_campaign.json")
    fp.parent.mkdir(parents=True, exist_ok=True)
    json.dump(obj=data, fp=fp.open(mode="w"))

    yield Output(value=(data, schema), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=schema
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

    schema = get_avro_record_schema(
        name="survey_response", fields=SURVEY_RESPONSE_FIELDS
    )

    fp = pathlib.Path("env/alchemer/survey_response.json")
    fp.parent.mkdir(parents=True, exist_ok=True)
    json.dump(obj=data, fp=fp.open(mode="w"))

    yield Output(value=(data, schema), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=schema
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

    schema = get_avro_record_schema(
        name="survey_response_disqualified", fields=SURVEY_RESPONSE_FIELDS
    )

    yield Output(value=(data, schema), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=schema
    )


survey_metadata_assets = [survey, survey_campaign, survey_question]

_all = [
    survey,
    survey_question,
    survey_campaign,
    survey_response,
    survey_response_disqualified,
]
