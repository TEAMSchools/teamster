import json
import os
import random

import pendulum
from alchemer import AlchemerSession
from dagster import build_resources, config_from_files
from fastavro import parse_schema, validation, writer

from teamster.core.alchemer.schema import ENDPOINT_FIELDS
from teamster.core.utils.functions import get_avro_record_schema
from teamster.core.utils.variables import LOCAL_TIME_ZONE

TEST_SURVEY_ID = 3370039


def check_schema(records, endpoint_name, key=None):
    print(f"\n{endpoint_name}")

    print("\tSAVING TO FILE...")
    with open(file=f"env/{endpoint_name.replace('/', '_')}.json", mode="w") as fp:
        json.dump(obj=records, fp=fp)
    print("\t\tSUCCESS")

    schema = get_avro_record_schema(
        name=endpoint_name, fields=ENDPOINT_FIELDS[endpoint_name]
    )
    # print(schema)

    print("\tPARSING SCHEMA...")
    parsed_schema = parse_schema(schema=schema)
    print("\t\tSUCCESS")

    if key is not None:
        sample_record = [r for r in records if "" in json.dumps(r)]
    else:
        sample_record = records[random.randint(a=0, b=(len(records) - 1))]
    # print("\tSAMPLE RECORD:")
    # print(sample_record)

    print("\tVALIDATING SINGLE RECORD...")
    assert validation.validate(datum=sample_record, schema=parsed_schema, strict=True)
    print("\t\tSUCCESS")

    print("\tVALIDATING ALL RECORDS...")
    assert validation.validate_many(records=records, schema=parsed_schema, strict=True)
    print("\t\tSUCCESS")

    print("\tWRITING ALL RECORDS...")
    with open(file="/dev/null", mode="wb") as fo:
        writer(
            fo=fo,
            schema=parsed_schema,
            records=records,
            codec="snappy",
            strict_allow_default=True,
        )
    print("\t\tSUCCESS")


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

        all_surveys = alchemer.survey.list()

        test_survey = all_surveys[random.randint(a=0, b=(len(all_surveys) - 1))]

        survey = alchemer.survey.get(TEST_SURVEY_ID or test_survey["id"])
        print(f"\nSURVEY: {survey.title}")
        print(f"ID: {survey.id}")

        check_schema(records=[survey.data], endpoint_name="survey")

        check_schema(records=survey.question.list(), endpoint_name="survey/question")

        check_schema(records=survey.campaign.list(), endpoint_name="survey/campaign")

        end_date = pendulum.now(tz="US/Eastern")
        if survey.id in [4561288]:
            start_date = end_date.subtract(months=1)
        else:
            start_date = end_date.subtract(months=120)

        survey_response = (
            survey.response.filter(
                "date_submitted", ">=", start_date.to_datetime_string()
            )
            .filter("date_submitted", "<", end_date.to_datetime_string())
            .list()
        )

        assert len(survey_response) > 0
        check_schema(records=survey_response, endpoint_name="survey/response")
