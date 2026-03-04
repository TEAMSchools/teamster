import pathlib
import subprocess
import time
from stat import S_ISDIR, S_ISREG

from dagster_shared import check
from dagster_ssh import SSHResource as DagsterSSHResource
from paramiko import SFTPAttributes, SFTPClient


class SSHResource(DagsterSSHResource):
    tunnel_remote_host: str | None = None
    test: bool = False

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

            if S_ISDIR(check.not_none(value=file.st_mode)):
                self._inner_listdir_attr_r(
                    sftp_client=sftp_client,
                    remote_dir=path,
                    exclude_dirs=exclude_dirs,
                    files=files,
                )
            elif S_ISREG(check.not_none(value=file.st_mode)):
                files.append((file, path))

        return files

    def open_ssh_tunnel(self):
        # trunk-ignore(bandit/B603)
        ssh_tunnel = subprocess.Popen(
            args=[
                "sshpass",
                (
                    f"-p{self.password}"
                    if self.test
                    else "-f/etc/secret-volume/powerschool_ssh_password.txt"
                ),
                "ssh",
                self.remote_host,
                f"-p{self.remote_port}",
                f"-l{self.username}",
                f"-L1521:{self.tunnel_remote_host}:1521",
                "-oHostKeyAlgorithms=+ssh-rsa",
                "-oStrictHostKeyChecking=accept-new",
                "-oConnectTimeout=10",
                "-N",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        while True:
            if ssh_tunnel.stdout is not None:
                stdout = ssh_tunnel.stdout.readline()
                self.log.debug(msg=stdout)

                if stdout in [
                    (
                        f"Warning: Permanently added '[{self.remote_host}]:"
                        f"{self.remote_port}' (RSA) to the list of known hosts.\r\n"
                    ).encode(),
                    b"A secure connection to your server has been established.\n",
                ]:
                    continue
                elif stdout == b"To disconnect, simply close this window.\n":
                    break
                else:
                    ssh_tunnel.kill()
                    raise Exception(stdout)

        time.sleep(1.0)

        return ssh_tunnel
