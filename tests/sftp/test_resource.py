import pathlib

from dagster_ssh import SSHResource
from pandas import read_csv

REMOTE_FILEPATH = ""


def test_foo():
    sftp = SSHResource()

    remote_filepath = pathlib.Path(REMOTE_FILEPATH)

    local_filepath = sftp.sftp_get(
        remote_filepath=str(remote_filepath),
        local_filepath=f"env/{remote_filepath.name}",
    )

    df = read_csv(filepatsh_or_buffer=local_filepath)

    print(df.dtypes.to_dict())
