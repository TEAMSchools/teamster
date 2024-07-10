import pathlib
import re
from stat import S_ISDIR, S_ISREG

from dagster import _check
from dagster_ssh import SSHResource as DagsterSSHResource
from paramiko import AutoAddPolicy, SFTPAttributes, SFTPClient, SSHClient
from sshtunnel import SSHTunnelForwarder


class SSHResource(DagsterSSHResource):
    # trunk-ignore(pyright/reportIncompatibleVariableOverride)
    remote_port: str = "22"
    tunnel_remote_host: str | None = None

    def get_connection(self) -> SSHClient:
        client = SSHClient()
        client.load_system_host_keys()

        if not self.allow_host_key_change:
            self.log.warning(
                (
                    "Remote Identification Change is not verified. "
                    "This won't protect against Man-In-The-Middle attacks"
                )
            )
            client.load_system_host_keys()

        if self.no_host_key_check:
            self.log.warning(
                (
                    "No Host Key Verification. "
                    "This won't protect against Man-In-The-Middle attacks"
                )
            )
            # Default is RejectPolicy
            # trunk-ignore(bandit/B507)
            client.set_missing_host_key_policy(AutoAddPolicy())

        if self.password and self.password.strip():
            client.connect(
                hostname=self.remote_host,
                username=self.username,
                password=self.password,
                key_filename=self.key_file,
                pkey=self._key_obj,
                timeout=self.timeout,
                auth_timeout=self.timeout,
                banner_timeout=self.timeout,
                channel_timeout=self.timeout,
                compress=self.compress,
                port=int(self.remote_port),
                # trunk-ignore(pyright/reportArgumentType)
                sock=self._host_proxy,
                look_for_keys=False,
            )
        else:
            client.connect(
                hostname=self.remote_host,
                username=self.username,
                key_filename=self.key_file,
                pkey=self._key_obj,
                timeout=self.timeout,
                auth_timeout=self.timeout,
                banner_timeout=self.timeout,
                channel_timeout=self.timeout,
                compress=self.compress,
                port=int(self.remote_port),
                # trunk-ignore(pyright/reportArgumentType)
                sock=self._host_proxy,
            )

        if self.keepalive_interval:
            transport = _check.not_none(client.get_transport())

            transport.set_keepalive(self.keepalive_interval)

        return client

    def get_tunnel(
        self, remote_port, remote_host="localhost", local_port=None
    ) -> SSHTunnelForwarder:
        if self.tunnel_remote_host is not None:
            remote_host = self.tunnel_remote_host

        return super().get_tunnel(
            remote_port=remote_port, remote_host=remote_host, local_port=local_port
        )

    def listdir_attr_r(self, remote_dir: str = ".", exclude_dirs: list | None = None):
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
        exclude_dirs: list,
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

    def match_sftp_files(
        self, remote_dir: str, remote_file: str, exclude_dirs: list[str] | None = None
    ):
        if exclude_dirs is None:
            exclude_dirs = []

        files = self.listdir_attr_r(remote_dir=remote_dir, exclude_dirs=exclude_dirs)

        if remote_dir == ".":
            pattern = remote_file
        else:
            pattern = f"{remote_dir}/{remote_file}"

        return [
            path
            for _, path in files
            if re.match(pattern=pattern, string=path) is not None
        ]
