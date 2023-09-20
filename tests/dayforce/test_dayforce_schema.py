import random

from fastavro import parse_schema, validation, writer
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.dayforce.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema


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


def test_employees():
    _test_schema(asset_name="employees", local_filepath="env/dayforce/employees.csv")


def test_employee_manager():
    _test_schema(
        asset_name="employee_manager",
        local_filepath="env/dayforce/employee_manager.csv",
    )


def test_employee_status():
    _test_schema(
        asset_name="employee_status", local_filepath="env/dayforce/employee_status.csv"
    )


def test_employee_work_assignment():
    _test_schema(
        asset_name="employee_work_assignment",
        local_filepath="env/dayforce/employee_work_assignment.csv",
    )
