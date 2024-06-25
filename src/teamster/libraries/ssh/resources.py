import pathlib
from stat import S_ISDIR, S_ISREG

from dagster import _check
from dagster_ssh import SSHResource as DagsterSSHResource
from paramiko import SFTPAttributes
from paramiko.sftp_client import SFTPClient
from sshtunnel import SSHTunnelForwarder


class SSHResource(DagsterSSHResource):
    # trunk-ignore(pyright/reportIncompatibleVariableOverride)
    remote_port: str = "22"
    tunnel_remote_host: str | None = None

    def get_tunnel(
        self, remote_port, remote_host="localhost", local_port=None
    ) -> SSHTunnelForwarder:
        if self.tunnel_remote_host is not None:
            remote_host = self.tunnel_remote_host

        return super().get_tunnel(
            remote_port=remote_port, remote_host=remote_host, local_port=local_port
        )

    def listdir_attr_r(self, remote_dir: str = "."):
        with self.get_connection() as connection:
            with connection.open_sftp() as sftp_client:
                return self._inner_listdir_attr_r(
                    sftp_client=sftp_client, remote_dir=remote_dir
                )

    def _inner_listdir_attr_r(
        self, sftp_client: SFTPClient, remote_dir: str, files: list | None = None
    ) -> list[tuple[SFTPAttributes, str]]:
        if files is None:
            files = []

        for file in sftp_client.listdir_attr(remote_dir):
            path = str(pathlib.Path(remote_dir) / file.filename)

            if S_ISDIR(_check.not_none(value=file.st_mode)):
                self._inner_listdir_attr_r(
                    sftp_client=sftp_client, remote_dir=path, files=files
                )
            elif S_ISREG(_check.not_none(value=file.st_mode)):
                files.append((file, path))

        return files
