import json
import random

from fastavro import parse_schema, validation, writer

from teamster.core.schoolmint.grow.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema


def _test(endpoint_name):
    with open(
        file=f"env/schoolmint/grow/{endpoint_name.replace('/', '__')}.json", mode="r"
    ) as fp:
        records = json.load(fp=fp)

    count = len(records)

    sample_record = records[random.randint(a=0, b=(count - 1))]
    print(sample_record)

    schema = get_avro_record_schema(
        name=endpoint_name, fields=ASSET_FIELDS[endpoint_name]
    )
    # print(schema)

    parsed_schema = parse_schema(schema)

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


def test_generic_tags_meetingtypes():
    _test("generic-tags/meetingtypes")


def test_schools():
    _test("schools")
