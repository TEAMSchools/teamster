import random

from dagster import EnvVar, build_resources, config_from_files
from fastavro import parse_schema, validation, writer

from teamster.core.schoolmint.grow.resources import SchoolMintGrowResource
from teamster.core.schoolmint.grow.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema

ASSET_CONFIG = config_from_files(["tests/schoolmint/config.yaml"])


def test_schoolmint_grow_schema():
    with build_resources(
        resources={
            "grow": SchoolMintGrowResource(
                client_id=EnvVar("SCHOOLMINT_GROW_CLIENT_ID"),
                client_secret=EnvVar("SCHOOLMINT_GROW_CLIENT_SECRET"),
                district_id=EnvVar("SCHOOLMINT_GROW_DISTRICT_ID"),
                api_response_limit=3200,
            )
        },
    ) as resources:
        grow: SchoolMintGrowResource = resources.grow

        for endpoint in ASSET_CONFIG["endpoints"]:
            endpoint_name = endpoint["asset_name"]

            data = grow.get(endpoint=endpoint_name, **endpoint.get("params", {}))

            records = data["data"]
            count = data["count"]

            if count > 0:
                schema = get_avro_record_schema(
                    name=endpoint_name, fields=ASSET_FIELDS[endpoint_name]
                )
                # print(schema)

                parsed_schema = parse_schema(schema)

                sample_record = records[random.randint(a=0, b=(count - 1))]
                print(sample_record)

                assert validation.validate(
                    datum=sample_record, schema=parsed_schema, strict=True
                )

                assert validation.validate_many(
                    records=records, schema=parsed_schema, strict=True
                )

                with open(file="/dev/null", mode="wb") as fo:
                    writer(
                        fo=fo,
                        schema=parsed_schema,
                        records=records,
                        codec="snappy",
                        strict_allow_default=True,
                    )
