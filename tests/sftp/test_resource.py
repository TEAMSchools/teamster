import pathlib
import zipfile

from dagster import build_resources, config_from_files
from dagster_ssh import ssh_resource
from pandas import read_csv

CODE_LOCATION = "kippmiami"
SOURCE_SYSTEM = "renlearn"
REMOTE_FILEPATH = "KIPP Miami.zip"
# "KIPPNewJersey - Star Math v2 RGP.csv"
ARCHIVE_FILE_PATH = "SR_v2.csv"

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

        if remote_filepath.suffix == ".zip":
            with zipfile.ZipFile(file=local_filepath) as zf:
                zf.extract(member=ARCHIVE_FILE_PATH, path="./env")

            local_filepath = f"./env/{ARCHIVE_FILE_PATH}"

        df = read_csv(filepath_or_buffer=local_filepath, low_memory=False)

        dtypes_dict = df.dtypes.to_dict()
        print(dtypes_dict)

        print(df.to_dict(orient="records")[0])
