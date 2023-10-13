import pathlib
import random

from dagster_ssh import ssh_resource
from fastavro import parse_schema, validation, writer
from numpy import nan
from pandas import read_csv

from dagster import build_resources, config_from_files
from teamster.core.clever.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema

SOURCE_SYSTEM = "clever_reporting"
CODE_LOCATION = "kipptaf"
REMOTE_FILEPATH = "daily-participation"
# "resource-usage"
DATE_PARTITION_KEY = "2023-05-01"
TYPE_PARTITION_KEY = "students"

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
        local_filepath = resources.sftp.sftp_get(
            remote_filepath=(
                f"{REMOTE_FILEPATH}/"
                f"{DATE_PARTITION_KEY}-{REMOTE_FILEPATH}-{TYPE_PARTITION_KEY}.csv"
            ),
            local_filepath=f"./env/{pathlib.Path(REMOTE_FILEPATH).name}",
        )

        df = read_csv(filepath_or_buffer=local_filepath, low_memory=False)
        df = df.replace({nan: None})

        count = df.shape[0]
        records = df.to_dict(orient="records")
        # dtypes_dict = df.dtypes.to_dict()
        # print(dtypes_dict)

        sample_record = records[random.randint(a=0, b=(count - 1))]
        # sample_record = [r for r in records if "" in json.dumps(obj=r)]
        # print(sample_record)

        schema = get_avro_record_schema(
            name=REMOTE_FILEPATH, fields=ASSET_FIELDS[REMOTE_FILEPATH]
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
