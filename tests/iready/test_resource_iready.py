import random
import re

from dagster import build_resources, config_from_files
from dagster_ssh import ssh_resource
from fastavro import parse_schema, validation, writer
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.iready.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema

SOURCE_SYSTEM = "iready"
CODE_LOCATION = "kipptaf"
REMOTE_FILEPATH = "/exports/nj-kipp_nj/Current_Year"
REMOTE_FILE_REGEX = r"personalized_instruction_by_lesson_(?P<subject>\w+).csv"
# r"instructional_usage_data_(?<subject>\w+).csv"
# r"diagnostic_results_(?P<subject>\w+).csv"
# r"diagnostic_and_instruction_(?P<subject>\w+)_ytd_window.csv"
ASSET_NAME = "personalized_instruction_by_lesson"
# "instructional_usage_data"
# "diagnostic_results"
# "diagnostic_and_instruction"

CONFIG_PATH = f"src/teamster/{CODE_LOCATION}/config/resources"


def test_schema():
    with build_resources(
        resources={"sftp": ssh_resource},
        resource_config={
            "sftp": {
                "config": config_from_files(
                    [f"{CONFIG_PATH}/sftp_{SOURCE_SYSTEM}.yaml"]
                )
            }
        },
    ) as resources:
        conn = resources.sftp.get_connection()
        with conn.open_sftp() as sftp_client:
            ls = sftp_client.listdir_attr(path=REMOTE_FILEPATH)
        conn.close()

        file_matches = [
            f
            for f in ls
            if re.match(pattern=REMOTE_FILE_REGEX, string=f.filename) is not None
        ]

        for f in file_matches:
            local_filepath = resources.sftp.sftp_get(
                remote_filepath=f"{REMOTE_FILEPATH}/{f.filename}",
                local_filepath=f"./env/{f.filename}",
            )

            df = read_csv(filepath_or_buffer=local_filepath, low_memory=False)
            df = df.replace({nan: None})
            df.rename(columns=lambda x: slugify(text=x, separator="_"), inplace=True)

            count = df.shape[0]
            records = df.to_dict(orient="records")
            print(df.dtypes.to_dict())

            sample_record = records[random.randint(a=0, b=(count - 1))]
            print(sample_record)

            schema = get_avro_record_schema(
                name=ASSET_NAME, fields=ASSET_FIELDS[ASSET_NAME]
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
