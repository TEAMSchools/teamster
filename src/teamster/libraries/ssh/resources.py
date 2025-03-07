import pathlib
from stat import S_ISDIR, S_ISREG

from dagster import _check
from dagster_ssh import SSHResource as DagsterSSHResource
from paramiko import SFTPAttributes, SFTPClient


class SSHResource(DagsterSSHResource):
    tunnel_remote_host: str | None = None

    def listdir_attr_r(
        self, remote_dir: str = ".", exclude_dirs: list[str] | None = None
    ):
        if exclude_dirs is None:
            exclude_dirs = []

        with self.get_connection() as connection:
            self.log.info("Opening SFTP session")
            with connection.open_sftp() as sftp_client:
                self.log.info(f"Listing of all files under {remote_dir}")
                return self._inner_listdir_attr_r(
                    sftp_client=sftp_client,
                    remote_dir=remote_dir,
                    exclude_dirs=exclude_dirs,
                )

    def _inner_listdir_attr_r(
        self,
        sftp_client: SFTPClient,
        remote_dir: str,
        exclude_dirs: list[str],
        files: list | None = None,
    ) -> list[tuple[SFTPAttributes, str]]:
        if files is None:
            files = []

        if remote_dir in exclude_dirs:
            return files

        self.log.info(f"Listing {remote_dir}")
        for file in sftp_client.listdir_attr(remote_dir):
            path = str(pathlib.Path(remote_dir) / file.filename)

            if S_ISDIR(_check.not_none(value=file.st_mode)):
                self._inner_listdir_attr_r(
                    sftp_client=sftp_client,
                    remote_dir=path,
                    exclude_dirs=exclude_dirs,
                    files=files,
                )
            elif S_ISREG(_check.not_none(value=file.st_mode)):
                files.append((file, path))

        return files
