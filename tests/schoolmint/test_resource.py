import random

from dagster import build_resources, config_from_files
from fastavro import parse_schema, validation

from teamster.core.resources.schoolmint import Grow, schoolmint_grow_resource
from teamster.core.schoolmint.schema import ENDPOINT_FIELDS, get_avro_record_schema

asset_config = config_from_files(["tests/config/schoolmint.yaml"])


def test_schoolmint_grow_schema():
    with build_resources(
        resources={"grow": schoolmint_grow_resource},
        resource_config={
            "grow": {
                "config": config_from_files(
                    ["src/teamster/core/config/resources/schoolmint.yaml"]
                )
            }
        },
    ) as resources:
        grow: Grow = resources.grow

        for endpoint in asset_config["endpoints"]:
            endpoint_name = endpoint["asset_name"]

            parsed_schema = parse_schema(
                get_avro_record_schema(
                    name=endpoint_name, fields=ENDPOINT_FIELDS[endpoint_name]
                )
            )

            data = grow.get(endpoint=endpoint_name, **endpoint.get("params", {}))

            records = data["data"]

            sample_record = records[random.randint(a=0, b=(data["count"] - 1))]
            print(sample_record)

            assert validation.validate(
                datum=sample_record, schema=parsed_schema, strict=True
            )

            assert validation.validate_many(
                records=records, schema=parsed_schema, strict=True
            )
