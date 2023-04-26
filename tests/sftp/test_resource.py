import pathlib
import random
import zipfile

from dagster import build_resources, config_from_files
from dagster_ssh import ssh_resource
from fastavro import parse_schema, validation, writer
from numpy import nan
from pandas import read_csv

from teamster.core.renlearn.schema import ENDPOINT_FIELDS
from teamster.core.utils.functions import get_avro_record_schema

CODE_LOCATION = "kippmiami"
SOURCE_SYSTEM = "renlearn"
ENDPOINT_NAME = "star_reading"
REMOTE_FILEPATH = "KIPP Miami.zip"
# "KIPPNewJersey - Generic AR Extract v2.csv"
# "KIPPNewJersey - Star Math v2 RGP.csv"
ARCHIVE_FILE_PATH = "SR_v2.csv"
# "SM_v2.csv"

CONFIG_PATH = f"src/teamster/{CODE_LOCATION}/config/resources"


def test_sftp():
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
        remote_filepath = pathlib.Path(REMOTE_FILEPATH)

        local_filepath = resources.sftp.sftp_get(
            remote_filepath=str(remote_filepath),
            local_filepath=f"./env/{remote_filepath.name}",
        )

        if ARCHIVE_FILE_PATH is not None:
            with zipfile.ZipFile(file=local_filepath) as zf:
                zf.extract(member=ARCHIVE_FILE_PATH, path="./env")

            local_filepath = f"./env/{ARCHIVE_FILE_PATH}"

        df = read_csv(filepath_or_buffer=local_filepath, low_memory=False)
        df = df.replace({nan: None})

        count = df.shape[0]
        records = df.to_dict(orient="records")
        # dtypes_dict = df.dtypes.to_dict()
        # print(dtypes_dict)

        schema = get_avro_record_schema(
            name=ENDPOINT_NAME, fields=ENDPOINT_FIELDS[ENDPOINT_NAME]
        )
        # print(schema)

        parsed_schema = parse_schema(schema)

        sample_record = records[random.randint(a=0, b=(count - 1))]
        # sample_record = [r for r in records if "" in json.dumps(r)]

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
