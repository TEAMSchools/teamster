import random
import re

from dagster import EnvVar, build_resources
from fastavro import parse_schema, validation, writer
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.ssh.resources import SSHConfigurableResource
from teamster.core.titan.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema

CODE_LOCATION = "KIPPCAMDEN"
# CODE_LOCATION = "KIPPNEWARK"
REMOTE_FILEPATH = "."
REMOTE_FILE_REGEX = r"persondata(?P<fiscal_year>\d{4})\.csv"
ASSET_NAME = "person_data"
# REMOTE_FILE_REGEX = r"incomeformdata(?P<fiscal_year>\d{4})\.csv"
# ASSET_NAME = "income_form_data"


def test_schema():
    with build_resources(
        resources={
            "ssh": SSHConfigurableResource(
                remote_host="sftp.titank12.com",
                username=EnvVar(f"{CODE_LOCATION}_TITAN_SFTP_USERNAME"),
                password=EnvVar(f"{CODE_LOCATION}_TITAN_SFTP_PASSWORD"),
            )
        }
    ) as resources:
        conn = resources.ssh.get_connection()
        with conn.open_sftp() as sftp_client:
            ls = sftp_client.listdir_attr(path=REMOTE_FILEPATH)
        conn.close()

        file_matches = [
            f
            for f in ls
            if re.match(pattern=REMOTE_FILE_REGEX, string=f.filename) is not None
        ]

        for f in file_matches:
            local_filepath = resources.ssh.sftp_get(
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
