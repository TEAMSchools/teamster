from dagster import EnvVar, build_init_resource_context
from dagster_shared import check

from teamster.libraries.ssh.resources import SSHResource


def _test_listdir_attr_r(ssh: SSHResource, remote_dir: str = "~"):
    ssh.setup_for_execution(context=build_init_resource_context())

    files = ssh.listdir_attr_r(remote_dir=remote_dir)

    for f in files:
        print(f)


def test_couchdrop():
    _test_listdir_attr_r(
        ssh=SSHResource(
            remote_host=check.not_none(value=EnvVar("COUCHDROP_SFTP_HOST").get_value()),
            username=EnvVar("COUCHDROP_SFTP_USERNAME").get_value(),
            password=EnvVar("COUCHDROP_SFTP_PASSWORD").get_value(),
        ),
        remote_dir=r"data-team",
    )


def test_coupa():
    _test_listdir_attr_r(
        ssh=SSHResource(
            remote_host=check.not_none(value=EnvVar("COUPA_SFTP_HOST").get_value()),
            username=EnvVar("COUPA_SFTP_USERNAME").get_value(),
            password=EnvVar("COUPA_SFTP_PASSWORD").get_value(),
        ),
        remote_dir=r"/Incoming/Users",
    )
