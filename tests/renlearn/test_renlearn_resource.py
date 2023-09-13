import zipfile

from dagster import EnvVar, build_resources

from teamster.core.ssh.resources import SSHConfigurableResource


def _test(code_location, remote_filepath, members):
    with build_resources(
        resources={
            "ssh": SSHConfigurableResource(
                remote_host="sftp.renaissance.com",
                username=EnvVar(f"{code_location}_RENLEARN_SFTP_USERNAME"),
                password=EnvVar(f"{code_location}_RENLEARN_SFTP_PASSWORD"),
            )
        },
    ) as resources:
        ssh: SSHConfigurableResource = resources.ssh

    local_filepath = ssh.sftp_get(
        remote_filepath=remote_filepath,
        local_filepath=f"./env/renlearn/{remote_filepath}",
    )

    if members is not None:
        with zipfile.ZipFile(file=local_filepath) as zf:
            for member in members:
                zf.extract(member=member, path=f"./env/renlearn/{code_location}")


def test_kippmiami():
    _test(
        code_location="KIPPMIAMI",
        remote_filepath="KIPP Miami.zip",
        members=["AR.csv", "SR.csv", "SM.csv"],
    )


def test_kippnj():
    _test(
        code_location="KIPPNJ",
        remote_filepath="KIPP TEAM & Family.zip",
        members=["AR.csv", "SR.csv", "SM.csv"],
    )
