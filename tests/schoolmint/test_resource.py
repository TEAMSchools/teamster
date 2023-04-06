import json
import random

from dagster import build_resources, config_from_files
from fastavro import parse_schema, validation, writer

from teamster.core.schoolmint.resources import Grow, schoolmint_grow_resource
from teamster.core.schoolmint.schema import ENDPOINT_FIELDS
from teamster.core.utils.functions import get_avro_record_schema

ASSET_CONFIG = config_from_files(["tests/schoolmint/config.yaml"])


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

        for endpoint in ASSET_CONFIG["endpoints"]:
            endpoint_name = endpoint["asset_name"]

            parsed_schema = parse_schema(
                get_avro_record_schema(
                    name=endpoint_name, fields=ENDPOINT_FIELDS[endpoint_name]
                )
            )

            data = grow.get(endpoint=endpoint_name, **endpoint.get("params", {}))

            records = data["data"]

            sample_record = records[random.randint(a=0, b=(data["count"] - 1))]
            # sample_record = [
            #     r for r in records if "observationTypesHidden" in json.dumps(r)
            # ]
            print(sample_record)

            assert validation.validate(
                datum=sample_record, schema=parsed_schema, strict=True
            )

            assert validation.validate_many(
                records=records, schema=parsed_schema, strict=True
            )

            with open(file="env/schoolmint_grow_test.json", mode="w+") as f:
                json.dump(obj=records, fp=f)

            with open(file="/dev/null", mode="wb") as fo:
                writer(
                    fo=fo,
                    schema=parsed_schema,
                    records=records,
                    codec="snappy",
                    strict_allow_default=True,
                )
