import pathlib
import zipfile

from dagster import EnvVar, build_resources

from teamster.core.ssh.resources import SSHConfigurableResource

CODE_LOCATION = "KIPPMIAMI"
TESTS = [
    {"remote_filepath": "KIPP Miami.zip", "members": ["AR.csv", "SR.csv", "SM.csv"]}
]


def test_resource():
    with build_resources(
        resources={
            "ssh": SSHConfigurableResource(
                remote_host="sftp.renaissance.com",
                username=EnvVar(f"{CODE_LOCATION}_RENLEARN_SFTP_USERNAME"),
                password=EnvVar(f"{CODE_LOCATION}_RENLEARN_SFTP_PASSWORD"),
            )
        },
    ) as resources:
        for test in TESTS:
            remote_filepath = pathlib.Path(test.get("remote_filepath"))

            local_filepath = resources.ssh.sftp_get(
                remote_filepath=str(remote_filepath),
                local_filepath=f"./env/{remote_filepath.name}",
            )

        members = test.get("members")

        if members is not None:
            with zipfile.ZipFile(file=local_filepath) as zf:
                for member in members:
                    zf.extract(member=member, path="./env")
