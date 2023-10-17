import json
import pathlib
import random

from fastavro import parse_schema, validation, writer
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.adp.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema

# ASSET_NAME = "TimeDetails"
# ASSET_NAME = "AccrualReportingPeriodSummary"
# ASSET_NAME = "pension_and_benefits_enrollments"
# ASSET_NAME = "comprehensive_benefits_report"
# ASSET_NAME = "additional_earnings_report"


def _test(filepath):
    filepath = pathlib.Path(filepath)
    asset_name = filepath.stem

    if filepath.suffix == "csv":
        df = read_csv(filepath_or_buffer=filepath, low_memory=False)
        df.replace({nan: None}, inplace=True)
        df.rename(columns=lambda x: slugify(text=x, separator="_"), inplace=True)
        # print(df.dtypes.to_dict())

        records = df.to_dict(orient="records")
        count = df.shape[0]
    else:
        records = json.load(fp=filepath.open())
        count = len(records)

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


def test_workers():
    _test(filepath="env/adp/workers.json")
