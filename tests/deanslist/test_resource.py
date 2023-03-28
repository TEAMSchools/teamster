import json
import random

from dagster import build_resources, config_from_files
from fastavro import parse_schema, validation, writer

from teamster.core.deanslist.schema import ENDPOINT_FIELDS, get_avro_record_schema
from teamster.core.resources.deanslist import DeansList, deanslist_resource

TEST_SCHOOL_ID = 126

asset_config = config_from_files(["tests/config/deanslist.yaml"])
resource_config = config_from_files(
    ["src/teamster/core/config/resources/deanslist.yaml"]
)


def test_deanslist_schema():
    with build_resources(
        resources={"deanslist": deanslist_resource},
        resource_config={"deanslist": {"config": resource_config}},
    ) as resources:
        dl: DeansList = resources.deanslist

        for endpoint in asset_config["endpoints"]:
            endpoint_name = endpoint["asset_name"]
            endpoint_version = endpoint["api_version"]

            parsed_schema = parse_schema(
                get_avro_record_schema(
                    name=endpoint_name,
                    fields=ENDPOINT_FIELDS[endpoint_name],
                    version=endpoint_version,
                )
            )

            row_count, records = dl.get_endpoint(
                endpoint=endpoint_name,
                api_version=endpoint_version,
                school_id=TEST_SCHOOL_ID,
                **endpoint.get("params", {}),
            )

            sample_record = records[random.randint(a=0, b=(row_count - 1))]
            # sample_record = [
            #     r for r in records if "" in json.dumps(r)
            # ]
            print(sample_record)

            assert validation.validate(
                datum=sample_record, schema=parsed_schema, strict=True
            )

            assert validation.validate_many(
                records=records, schema=parsed_schema, strict=True
            )

            with open(file="env/deanslist_test.json", mode="w+") as f:
                json.dump(obj=records, fp=f)

            with open(file="/dev/null", mode="wb") as fo:
                writer(
                    fo=fo,
                    schema=parsed_schema,
                    records=records,
                    codec="snappy",
                    strict_allow_default=True,
                )
