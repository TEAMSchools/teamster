# trunk-ignore-all(ruff/E501)

import random

from fastavro import parse_schema, validation, writer
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.pearson.schema import ASSET_FIELDS
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


def test_parcc():
    _test_schema(
        asset_name="parcc",
        # local_filepath="env/parcc/pcspr22_NJ-807325_District_Summative_Record_File_Spring.csv",
        # local_filepath="env/parcc/pcspr19_NJ-807325_District_Summative_Record_File_Spring.csv",
        # local_filepath="env/parcc/PC_pcspr18_NJ-807325-965_PARCC_School_Summative_Record_File_Spring.csv",
        # local_filepath="env/parcc/PC_pcspr17_NJ-807325-965_PARCC_School_Summative_Record_File_Spring.csv",
        # local_filepath=("env/parcc/PC_pcspr16_NJ-807325-965_PARCC_School_Summative_Record_File_Spring.csv"),
        # local_filepath="env/parcc/pcspr23_NJ-807325_District_Summative_Record_File_Spring.csv",
        # local_filepath="env/parcc/PC_pcspr16_NJ-071799_PARCC_District_Summative_Record_File_Spring.csv",
        # local_filepath="env/parcc/PC_pcspr17_NJ-071799_PARCC_District_Summative_Record_File_Spring.csv",
        # local_filepath="env/parcc/PC_pcspr18_NJ-071799-111_PARCC_School_Summative_Record_File_Spring.csv",
        # local_filepath="env/parcc/pcspr19_NJ-071799_District_Summative_Record_File_Spring.csv",
        # local_filepath="env/parcc/pcspr22_NJ-071799_District_Summative_Record_File_Spring.csv",
        local_filepath="env/parcc/pcspr23_NJ-071799_District_Summative_Record_File_Spring.csv",
    )


def test_njsla():
    _test_schema(
        asset_name="njsla",
        # local_filepath="env/njsla/njs22_NJ-807325_District_Summative_Record_File_Spring.csv",
        # local_filepath="env/njsla/njs23_NJ-807325_District_Summative_Record_File_Spring.csv",
        # local_filepath="env/njsla/njs22_NJ-071799_District_Summative_Record_File_Spring.csv",
        # local_filepath="env/njsla/njs23_NJ-071799_District_Summative_Record_File_Spring.csv",
    )


def test_njgpa():
    _test_schema(
        asset_name="njgpa",
        # local_filepath="env/njgpa/pcspr22_NJ-807325_District_Summative_Record_File_GPA_Spring.csv",
        # local_filepath="env/njgpa/pcspr23_NJ-807325_District_Summative_Record_File_GPA_Spring.csv",
        # local_filepath="env/njgpa/pcspr23_NJ-071799_District_Summative_Record_File_GPA_Spring.csv",
    )
