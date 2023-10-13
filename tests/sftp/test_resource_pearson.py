import re

from dagster import EnvVar, build_resources
from teamster.core.ssh.resources import SSHConfigurableResource


def _test_resource(remote_filepath, remote_file_regex):
    with build_resources(
        resources={
            "ssh": SSHConfigurableResource(
                remote_host="kipptaf.couchdrop.io",
                username=EnvVar("COUCHDROP_SFTP_USERNAME"),
                password=EnvVar("COUCHDROP_SFTP_PASSWORD"),
            )
        }
    ) as resources:
        ssh: SSHConfigurableResource = resources.ssh

    conn = ssh.get_connection()

    with conn.open_sftp() as sftp_client:
        ls = sftp_client.listdir_attr(path=remote_filepath)

    conn.close()

    file_matches = [
        f
        for f in ls
        if re.match(pattern=remote_file_regex, string=f.filename) is not None
    ]

    for f in file_matches:
        ssh.sftp_get(
            remote_filepath=f"{remote_filepath}/{f.filename}",
            local_filepath=f"./env/{f.filename}",
        )


def test_parcc():
    code_location = "kippcamden"
    # code_location = "kippnewark"

    _test_resource(
        remote_filepath=f"/teamster-{code_location}/couchdrop/pearson/parcc",
        remote_file_regex=r".*\.csv",
    )


def test_njsla():
    code_location = "kippcamden"
    # code_location = "kippnewark"

    _test_resource(
        remote_filepath=f"/teamster-{code_location}/couchdrop/pearson/njsla",
        remote_file_regex=r".*\.csv",
    )


def test_njgpa():
    code_location = "kippcamden"
    # code_location = "kippnewark"

    _test_resource(
        remote_filepath=f"/teamster-{code_location}/couchdrop/pearson/njgpa",
        remote_file_regex=r".*\.csv",
    )
