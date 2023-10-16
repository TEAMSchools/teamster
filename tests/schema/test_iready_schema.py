import random

from fastavro import parse_schema, validation, writer
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.iready.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema


def _test(local_filepath, asset_name):
    df = read_csv(filepath_or_buffer=local_filepath, low_memory=False)
    df.replace({nan: None}, inplace=True)
    df.rename(
        columns=lambda x: slugify(
            text=x, separator="_", replacements=[["%", "percent"]]
        ),
        inplace=True,
    )

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


def test_diagnostic_results():
    _test(
        local_filepath="./env/iready/diagnostic_results_ela.csv",
        asset_name="diagnostic_results",
    )

    _test(
        local_filepath="./env/iready/diagnostic_results_math.csv",
        asset_name="diagnostic_results",
    )


def test_personalized_instruction_by_lesson():
    _test(
        local_filepath="./env/iready/personalized_instruction_by_lesson_ela.csv",
        asset_name="personalized_instruction_by_lesson",
    )

    _test(
        local_filepath="./env/iready/personalized_instruction_by_lesson_math.csv",
        asset_name="personalized_instruction_by_lesson",
    )


def test_instructional_usage_data():
    _test(
        local_filepath="./env/iready/instructional_usage_data_ela.csv",
        asset_name="instructional_usage_data",
    )

    _test(
        local_filepath="./env/iready/instructional_usage_data_math.csv",
        asset_name="instructional_usage_data",
    )
