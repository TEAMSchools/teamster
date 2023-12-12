import pathlib
from stat import S_ISDIR, S_ISREG

from dagster_ssh import SSHResource
from sshtunnel import SSHTunnelForwarder


class SSHResource(SSHResource):
    remote_port = 22
    tunnel_remote_host: str = None

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

    def listdir_attr_r(self, remote_dir: str, files: list = []):
        try:
            conn = self.get_connection()
            try:
                sftp_client = conn.open_sftp()
                files = self._listdir_attr_r(
                    sftp_client=sftp_client, remote_dir=remote_dir, files=files
                )
            finally:
                sftp_client.close()
        finally:
            conn.close()
            return files

    def _listdir_attr_r(self, sftp_client, remote_dir: str, files: list = []):
        for file in sftp_client.listdir_attr(remote_dir):
            try:
                filepath = str(pathlib.Path(remote_dir) / file.filepath)
            except AttributeError:
                filepath = str(pathlib.Path(remote_dir) / file.filename)

            if S_ISDIR(file.st_mode):
                self._listdir_attr_r(
                    sftp_client=sftp_client, remote_dir=filepath, files=files
                )
            elif S_ISREG(file.st_mode):
                file.filepath = filepath
                files.append(file)

        return files
