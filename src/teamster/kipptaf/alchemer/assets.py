import json
import time

import pendulum
from dagster import DynamicPartitionsDefinition, OpExecutionContext, Output, asset
from requests.exceptions import HTTPError

from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_record_schema,
    get_avro_schema_valid_check_spec,
)

from .. import CODE_LOCATION
from .resources import AlchemerResource
from .schema import ASSET_FIELDS

GROUP_NAME = "alchemer"
IO_MANAGER_KEY = "io_manager_gcs_avro"

KEY_PREFIX = [CODE_LOCATION, GROUP_NAME]
PARTITIONS_DEF = DynamicPartitionsDefinition(name=f"{CODE_LOCATION}_alchemer_survey_id")


@asset(
    key=[*KEY_PREFIX, "survey"],
    io_manager_key=IO_MANAGER_KEY,
    partitions_def=PARTITIONS_DEF,
    group_name=GROUP_NAME,
    check_specs=[get_avro_schema_valid_check_spec([*KEY_PREFIX, "survey"])],
)
def survey(context: OpExecutionContext, alchemer: AlchemerResource):
    survey = alchemer._client.survey.get(id=context.partition_key)

    data_str = json.dumps(obj=survey.data).replace("soft-required", "soft_required")

    data = [json.loads(s=data_str)]
    schema = get_avro_record_schema(name="survey", fields=ASSET_FIELDS["survey"])

    yield Output(value=(data, schema), metadata={"record_count": 1})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=schema
    )


@asset(
    key=[*KEY_PREFIX, "survey_question"],
    io_manager_key=IO_MANAGER_KEY,
    partitions_def=PARTITIONS_DEF,
    group_name=GROUP_NAME,
    check_specs=[get_avro_schema_valid_check_spec([*KEY_PREFIX, "survey_question"])],
)
def survey_question(context: OpExecutionContext, alchemer: AlchemerResource):
    survey = alchemer._client.survey.get(id=context.partition_key)

    data = survey.question.list(params={"resultsperpage": 500})

    data_str = json.dumps(obj=data).replace("soft-required", "soft_required")

    data = json.loads(s=data_str)
    schema = get_avro_record_schema(
        name="survey_question", fields=ASSET_FIELDS["survey_question"]
    )

    yield Output(value=(data, schema), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=schema
    )


@asset(
    key=[*KEY_PREFIX, "survey_campaign"],
    io_manager_key=IO_MANAGER_KEY,
    partitions_def=PARTITIONS_DEF,
    group_name=GROUP_NAME,
    check_specs=[get_avro_schema_valid_check_spec([*KEY_PREFIX, "survey_campaign"])],
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

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=schema
    )


@asset(
    key=[*KEY_PREFIX, "survey_response"],
    io_manager_key=IO_MANAGER_KEY,
    partitions_def=DynamicPartitionsDefinition(
        name=f"{CODE_LOCATION}_alchemer_survey_response"
    ),
    group_name=GROUP_NAME,
    check_specs=[get_avro_schema_valid_check_spec([*KEY_PREFIX, "survey_response"])],
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

    schema = get_avro_record_schema(
        name="survey_response", fields=ASSET_FIELDS["survey_response"]
    )

    yield Output(value=(data, schema), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=schema
    )


survey_metadata_assets = [survey, survey_campaign, survey_question]

__all__ = [
    survey,
    survey_question,
    survey_campaign,
    survey_response,
]
