from dagster import build_resources, config_from_files
from fastavro import parse_schema, validation

from teamster.core.deanslist.schema import ENDPOINT_FIELDS, get_avro_record_schema
from teamster.core.resources.deanslist import DeansList, deanslist_resource

TEST_SCHOOL_ID = 126

config = config_from_files(["tests/config/deanslist.yaml"])
resource_config = config["resource"]
asset_config = config["asset"]


def test_deanslist_schema():
    with build_resources(
        resources={"deanslist": deanslist_resource},
        resource_config={"deanslist": {"config": resource_config}},
    ) as resources:
        dl: DeansList = resources.deanslist

        for endpoint in asset_config["endpoints"]:
            endpoint_name = endpoint["asset_name"]
            endpoint_version = endpoint["api_version"]

            row_count, records = dl.get_endpoint(
                endpoint=endpoint_name,
                api_version=endpoint_version,
                school_id=TEST_SCHOOL_ID,
                **endpoint.get("params", {}),
            )

            print(f"COUNT: {row_count}")

            assert validation.validate_many(
                records=records,
                schema=parse_schema(
                    get_avro_record_schema(
                        name=endpoint_name,
                        fields=ENDPOINT_FIELDS[endpoint_name],
                        version=endpoint_version,
                    )
                ),
                strict=True,
            )
