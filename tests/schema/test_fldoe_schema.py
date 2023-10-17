import random

from fastavro import parse_schema, validation, writer
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.fldoe.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema

SCHOOL_YEAR_TERM = "SY24PM1"

LOCAL_FILEPATHS = [
    f"env/fldoe/KIPPMIAMI-LIBERTYCITY_Grade3FASTELAReading_StudentData_{SCHOOL_YEAR_TERM}.csv",
    f"env/fldoe/KIPPMIAMI-LIBERTYCITY_Grade3FASTMathematics_StudentData_{SCHOOL_YEAR_TERM}.csv",
    f"env/fldoe/KIPPMIAMI-LIBERTYCITY_Grade4FASTELAReading_StudentData_{SCHOOL_YEAR_TERM}.csv",
    f"env/fldoe/KIPPMIAMI-LIBERTYCITY_Grade4FASTMathematics_StudentData_{SCHOOL_YEAR_TERM}.csv",
    f"env/fldoe/KIPPMIAMI-LIBERTYCITY_Grade5FASTELAReading_StudentData_{SCHOOL_YEAR_TERM}.csv",
    f"env/fldoe/KIPPMIAMI-LIBERTYCITY_Grade5FASTMathematics_StudentData_{SCHOOL_YEAR_TERM}.csv",
    f"env/fldoe/KIPPMIAMI-LIBERTYCITY_Grade6FASTELAReading_StudentData_{SCHOOL_YEAR_TERM}.csv",
    f"env/fldoe/KIPPMIAMI-LIBERTYCITY_Grade6FASTMathematics_StudentData_{SCHOOL_YEAR_TERM}.csv",
    f"env/fldoe/KIPPMIAMI-LIBERTYCITY_Grade7FASTELAReading_StudentData_{SCHOOL_YEAR_TERM}.csv",
    f"env/fldoe/KIPPMIAMI-LIBERTYCITY_Grade7FASTMathematics_StudentData_{SCHOOL_YEAR_TERM}.csv",
    f"env/fldoe/KIPPMIAMI-LIBERTYCITY_Grade8FASTELAReading_StudentData_{SCHOOL_YEAR_TERM}.csv",
    f"env/fldoe/KIPPMIAMI-LIBERTYCITY_Grade8FASTMathematics_StudentData_{SCHOOL_YEAR_TERM}.csv",
]


def _test_schema(local_filepath, asset_name):
    df = read_csv(filepath_or_buffer=local_filepath, low_memory=False)

    df.replace({nan: None}, inplace=True)
    df.rename(columns=lambda x: slugify(text=x, separator="_"), inplace=True)

    # print(df.dtypes.to_dict())

    count = df.shape[0]
    records = df.to_dict(orient="records")

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


def test_fast():
    for local_filepath in LOCAL_FILEPATHS:
        _test_schema(asset_name="fast", local_filepath=local_filepath)
