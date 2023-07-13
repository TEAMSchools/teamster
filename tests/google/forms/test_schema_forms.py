import json
import random

from fastavro import parse_schema, validation, writer

from teamster.core.google.schema.forms import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema

TESTS = [
    "form",
    "responses",
]


def test_schema():
    for asset_name in TESTS:
        print(asset_name)

        schema = get_avro_record_schema(
            name=asset_name, fields=ASSET_FIELDS[asset_name]
        )
        # print(schema)

        parsed_schema = parse_schema(schema)

        with open(file=f"env/{asset_name}.json", mode="r") as fp:
            records = json.load(fp=fp)

        if isinstance(records, dict):
            records = [records]

        count = len(records)

        sample_record = records[random.randint(a=0, b=(count - 1))]
        # print(sample_record)

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
