import random

from fastavro import parse_schema, validation, writer
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.smartrecruiters.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema

ASSET_NAME = "offered_hired"
# "applicants"
# "applications"


def test_schema():
    df = read_csv(filepath_or_buffer=f"env/{ASSET_NAME}.csv", low_memory=False)
    df = df.replace({nan: None})
    df.rename(columns=lambda x: slugify(text=x, separator="_"), inplace=True)

    count = df.shape[0]
    records = df.to_dict(orient="records")
    print(df.dtypes.to_dict())

    sample_record = records[random.randint(a=0, b=(count - 1))]
    print(sample_record)

    schema = get_avro_record_schema(name=ASSET_NAME, fields=ASSET_FIELDS[ASSET_NAME])
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
