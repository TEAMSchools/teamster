import random

from fastavro import parse_schema, validation, writer
from numpy import nan
from pandas import read_csv

from teamster.core.renlearn.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema


def _test(local_filepath, asset_name):
    df = read_csv(filepath_or_buffer=local_filepath, low_memory=False).replace(
        {nan: None}
    )

    count = df.shape[0]
    records = df.to_dict(orient="records")
    # dtypes_dict = df.dtypes.to_dict()
    # print(dtypes_dict)

    schema = get_avro_record_schema(name=asset_name, fields=ASSET_FIELDS[asset_name])
    # print(schema)

    parsed_schema = parse_schema(schema)

    sample_record = records[random.randint(a=0, b=(count - 1))]
    # sample_record = [r for r in records if "" in json.dumps(obj=r)]

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


def test_ar():
    _test(local_filepath="env/renlearn/KIPPNJ/AR.csv", asset_name="accelerated_reader")


def test_sm():
    _test(local_filepath="env/renlearn/KIPPNJ/SM.csv", asset_name="star_math")


def test_sr():
    _test(local_filepath="env/renlearn/KIPPMIAMI/SR.csv", asset_name="star_reading")
