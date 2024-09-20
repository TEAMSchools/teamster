import pathlib
from stat import S_ISDIR, S_ISREG

from dagster import _check
from dagster_ssh import SSHResource as DagsterSSHResource
from paramiko import AutoAddPolicy, SFTPAttributes, SFTPClient, SSHClient

from teamster.libraries.ssh.sshtunnel.forwarder import SSHTunnelForwarder


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

    # trunk-ignore(pyright/reportIncompatibleMethodOverride)
    def get_tunnel(
        self, remote_port, remote_host="localhost", local_port=None
    ) -> SSHTunnelForwarder:
        _check.str_param(obj=remote_host, param_name="remote_host")
        _check.int_param(obj=remote_port, param_name="remote_port")
        _check.opt_int_param(obj=local_port, param_name="local_port")

        if self.tunnel_remote_host is not None:
            remote_bind_address = (self.tunnel_remote_host, remote_port)
        else:
            remote_bind_address = (remote_host, remote_port)

        if local_port is not None:
            local_bind_address = ("localhost", local_port)
        else:
            local_bind_address = ("localhost",)

        # Will prefer key string if specified, otherwise use the key file
        if self._key_obj and self.key_file:
            self.log.warning(
                "SSHResource: key_string and key_file both specified as config. "
                "Using key_string."
            )

        pkey = self._key_obj if self._key_obj else self.key_file

        if self.password and self.password.strip():
            client = SSHTunnelForwarder(
                ssh_address_or_host=self.remote_host,
                ssh_port=int(self.remote_port),
                ssh_username=self.username,
                ssh_password=self.password,
                ssh_pkey=pkey,
                ssh_proxy=self._host_proxy,
                local_bind_address=local_bind_address,
                remote_bind_address=remote_bind_address,
                logger=self._logger,
            )
        else:
            client = SSHTunnelForwarder(
                ssh_address_or_host=self.remote_host,
                ssh_port=int(self.remote_port),
                ssh_username=self.username,
                ssh_pkey=pkey,
                ssh_proxy=self._host_proxy,
                local_bind_address=local_bind_address,
                remote_bind_address=(remote_host, remote_port),
                host_pkey_directories=[],
                logger=self._logger,
            )

        return client

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
