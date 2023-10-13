import re

from dagster import EnvVar, build_resources

from teamster.core.ssh.resources import SSHConfigurableResource

CODE_LOCATION = "KIPPCAMDEN"
TESTS = [
    {
        "remote_filepath": ".",
        "remote_file_regex": r"persondata(?P<fiscal_year>\d{4})\.csv",
    },
    {
        "remote_filepath": ".",
        "remote_file_regex": r"incomeformdata(?P<fiscal_year>\d{4})\.csv",
    },
]


def test_schema():
    for test in TESTS:
        remote_filepath = test["remote_filepath"]

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
                ls = sftp_client.listdir_attr(path=remote_filepath)

            conn.close()

            file_matches = [
                f
                for f in ls
                if re.match(pattern=test["remote_file_regex"], string=f.filename)
                is not None
            ]

            for f in file_matches:
                resources.ssh.sftp_get(
                    remote_filepath=f"{remote_filepath}/{f.filename}",
                    local_filepath=f"./env/{f.filename}",
                )
