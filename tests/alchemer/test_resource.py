import json
import os
import random

from alchemer import AlchemerSession
from dagster import build_resources, config_from_files
from fastavro import parse_schema, validation, writer

from teamster.core.alchemer.schema import ENDPOINT_FIELDS
from teamster.core.utils.functions import get_avro_record_schema
from teamster.core.utils.variables import LOCAL_TIME_ZONE

TEST_SURVEY_ID = 5300913


def check_schema(records, endpoint_name, key=None):
    with open(file=f"env/{endpoint_name}.json", mode="w") as fp:
        json.dump(obj=records, fp=fp)

    schema = get_avro_record_schema(
        name=endpoint_name, fields=ENDPOINT_FIELDS[endpoint_name]
    )

    parsed_schema = parse_schema(schema=schema)

    if key is not None:
        sample_record = [r for r in records if "" in json.dumps(r)]
    else:
        sample_record = records[random.randint(a=0, b=(len(records) - 1))]

    assert validation.validate(datum=sample_record, schema=parsed_schema, strict=True)

    assert validation.validate_many(records=records, schema=parsed_schema, strict=True)

    with open(file="/dev/null", mode="wb") as fo:
        writer(
            fo=fo,
            schema=parsed_schema,
            records=records,
            codec="snappy",
            strict_allow_default=True,
        )


def test_alchemer_schema():
    with build_resources(
        resources={
            "alchemer": AlchemerSession(
                api_token=os.getenv("ALCHEMER_API_TOKEN"),
                api_token_secret=os.getenv("ALCHEMER_API_TOKEN_SECRET"),
                time_zone=LOCAL_TIME_ZONE,
                **config_from_files(
                    ["src/teamster/core/config/resources/alchemer.yaml"]
                ),
            )
        },
    ) as resources:
        alchemer: AlchemerSession = resources.alchemer

        survey = alchemer.survey.get(TEST_SURVEY_ID)
        check_schema(records=[survey.data], endpoint_name="survey")
