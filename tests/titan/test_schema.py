import random

from fastavro import parse_schema, validation, writer
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.titan.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema

ACADEMIC_YEAR = 2020
TESTS = [
    {
        "local_filepath": f"env/persondata{ACADEMIC_YEAR}.csv",
        "asset_name": "person_data",
    },
    # {
    #     "local_filepath": f"env/incomeformdata{ACADEMIC_YEAR}.csv",
    #     "asset_name": "income_form_data",
    # },
]


def test_schema():
    for test in TESTS:
        print(test)
        asset_name = test["asset_name"]

        df = read_csv(filepath_or_buffer=test["local_filepath"], low_memory=False)
        df = df.replace({nan: None})
        df.rename(columns=lambda x: slugify(text=x, separator="_"), inplace=True)

        count = df.shape[0]
        records = df.to_dict(orient="records")
        # print(df.dtypes.to_dict())

        sample_record = records[random.randint(a=0, b=(count - 1))]
        # print(sample_record)

        schema = get_avro_record_schema(
            name=asset_name, fields=ASSET_FIELDS[asset_name]
        )
        # print(schema)

        parsed_schema = parse_schema(schema)

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
