import json
import random

import pendulum
from dagster import build_resources, config_from_files
from fastavro import parse_schema, validation, writer

from teamster.core.deanslist.resources import DeansList, deanslist_resource
from teamster.core.deanslist.schema import ENDPOINT_FIELDS
from teamster.core.utils.functions import get_avro_record_schema

asset_config = config_from_files(["tests/deanslist/config.yaml"])
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
                    fields=ENDPOINT_FIELDS[endpoint_name][endpoint_version],
                )
            )

            endpoint_content = dl.get_endpoint(
                endpoint=endpoint_name,
                api_version=endpoint_version,
                school_id=asset_config["school_id"],
                UpdatedSince=pendulum.now().to_date_string(),
                **endpoint.get("params", {}),
            )

            row_count = endpoint_content["row_count"]
            records = endpoint_content["data"]

            sample_record = records[random.randint(a=0, b=(row_count - 1))]
            # sample_record = [r for r in records if "PointValue" in json.dumps(r)]
            print(sample_record)

            with open(file="env/deanslist_test.json", mode="w+") as f:
                json.dump(obj=records, fp=f)

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
