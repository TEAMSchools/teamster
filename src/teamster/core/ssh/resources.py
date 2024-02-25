import pathlib
from stat import S_ISDIR, S_ISREG

from dagster_ssh import SSHResource as DagsterSSHResource
from paramiko.sftp_client import SFTPClient
from sshtunnel import SSHTunnelForwarder


class SSHResource(DagsterSSHResource):
    remote_port: int = 22
    tunnel_remote_host: str | None = None

    def get_tunnel(
        self, remote_port, remote_host=None, local_port=None
    ) -> SSHTunnelForwarder:
        if remote_host is not None:
            pass
        elif self.tunnel_remote_host is not None:
            remote_host = self.tunnel_remote_host
        else:
            remote_host = "localhost"

        return super().get_tunnel(
            remote_port=remote_port, remote_host=remote_host, local_port=local_port
        )

    def listdir_attr_r(self, remote_dir: str, files: list | None = None):
        if files is None:
            files = []

        with self.get_connection() as conn:
            try:
                with conn.open_sftp() as sftp_client:
                    try:
                        files = self._listdir_attr_r(
                            sftp_client=sftp_client, remote_dir=remote_dir, files=files
                        )
                    finally:
                        sftp_client.close()
            finally:
                conn.close()

        return files

    def _listdir_attr_r(
        self, sftp_client: SFTPClient, remote_dir: str, files: list | None = None
    ):
        if files is None:
            files = []

        for file in sftp_client.listdir_attr(remote_dir):
            try:
                filepath = str(pathlib.Path(remote_dir) / file.filepath)  # type: ignore
            except AttributeError:
                filepath = str(pathlib.Path(remote_dir) / file.filename)

            if S_ISDIR(file.st_mode):  # type: ignore
                self._listdir_attr_r(
                    sftp_client=sftp_client, remote_dir=filepath, files=files
                )
            elif S_ISREG(file.st_mode):  # type: ignore
                file.filepath = filepath  # type: ignore
                files.append(file)

        return files
