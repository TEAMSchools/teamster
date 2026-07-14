from dagster import EnvVar, build_init_resource_context
from dagster_shared import check

from teamster.core.resources import get_powerschool_ssh_resource
from teamster.libraries.ssh.resources import SSHResource


def test_get_powerschool_ssh_resource_port_is_lazy(monkeypatch):
    """`PS_SSH_PORT` must resolve at resource init, not at construction.

    Regression: the factory previously called
    ``EnvVar("PS_SSH_PORT").get_value()`` eagerly, so constructing the resource
    (which happens at district ``definitions.py`` module load) raised when the
    variable was unset — e.g. in a codespace. See ``src/teamster/CLAUDE.md``.
    """
    monkeypatch.delenv("PS_SSH_PORT", raising=False)

    # Construction must not touch the environment.
    resource = get_powerschool_ssh_resource()

    # At resource-init time the port resolves to a real int.
    monkeypatch.setenv("PS_SSH_HOST", "ps.example.org")
    monkeypatch.setenv("PS_SSH_PORT", "1521")
    monkeypatch.setenv("PS_SSH_USERNAME", "svc_ps")
    monkeypatch.setenv("PS_SSH_REMOTE_BIND_HOST", "oracle.internal")

    initialized = resource.process_config_and_initialize()

    assert initialized.remote_port == 1521
    assert isinstance(initialized.remote_port, int)


def _test_listdir_attr_r(ssh: SSHResource, remote_dir: str = "~"):
    ssh.setup_for_execution(context=build_init_resource_context())

    with (
        ssh.get_connection() as connection,
        connection.open_sftp() as sftp_client,
    ):
        files = ssh.listdir_attr_r(sftp_client=sftp_client, remote_dir=remote_dir)

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
