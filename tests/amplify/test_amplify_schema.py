import random

from fastavro import parse_schema, validation, writer
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.amplify.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema


def _test(asset_name, file_name):
    df = read_csv(filepath_or_buffer=file_name, low_memory=False)

    df.replace({nan: None}, inplace=True)
    df.rename(columns=lambda x: slugify(text=x, separator="_"), inplace=True)
    # print(df.dtypes.to_dict())

    count = df.shape[0]
    records = df.to_dict(orient="records")

    sample_record = records[random.randint(a=0, b=(count - 1))]
    # print(sample_record)

    schema = get_avro_record_schema(name=asset_name, fields=ASSET_FIELDS[asset_name])
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


def test_schema_bm():
    _test(asset_name="benchmark_student_summary", file_name="env/amplify/BM.csv")


def test_schema_pm():
    _test(asset_name="pm_student_summary", file_name="env/amplify/PM.csv")
