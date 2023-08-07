import json
import random

from fastavro import parse_schema, validation, writer

from teamster.core.google.directory.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema


def _test_schema(asset_name):
    print(asset_name)

    with open(file=f"env/{asset_name}.json", mode="r") as fp:
        records = json.load(fp=fp)

    schema = get_avro_record_schema(name=asset_name, fields=ASSET_FIELDS[asset_name])
    # print(schema)

    parsed_schema = parse_schema(schema)

    count = len(records)

    sample_record = records[random.randint(a=0, b=(count - 1))]
    # print(sample_record)

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


def test_users():
    _test_schema("users")


def test_groups():
    _test_schema("groups")


def test_members():
    _test_schema("members")


def test_roles():
    _test_schema("roles")


def test_role_assignments():
    _test_schema("role_assignments")


def test_orgunits():
    _test_schema("orgunits")
