from dagster import ConfigurableResource, InitResourceContext
from dagster_ssh import SSHResource
from pydantic import PrivateAttr


class SSHConfigurableResource(ConfigurableResource):
    remote_host: str
    remote_port: str = "22"
    username: str = None
    password: str = None
    key_file: str = None
    key_string: str = None
    timeout: int = 10
    keepalive_interval: int = 30
    compress: bool = True
    no_host_key_check: bool = True
    allow_host_key_change: bool = False
    tunnel_remote_host: str = "localhost"

    _internal_resource: SSHResource = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._internal_resource = SSHResource(
            remote_host=self.remote_host,
            remote_port=int(self.remote_port),
            username=self.username,
            password=self.password,
            key_file=self.key_file,
            key_string=self.key_string,
            timeout=self.timeout,
            keepalive_interval=self.keepalive_interval,
            compress=self.compress,
            no_host_key_check=self.no_host_key_check,
            allow_host_key_change=self.allow_host_key_change,
            logger=self.get_resource_context().log,
        )

        return super().setup_for_execution(context)

    def get_connection(self):
        return self._internal_resource.get_connection()

    def get_tunnel(self, remote_port, remote_host=None, local_port=None):
        if remote_host is None:
            remote_host = self.tunnel_remote_host

        return self._internal_resource.get_tunnel(
            remote_port=remote_port, remote_host=remote_host, local_port=local_port
        )

    def sftp_get(self, remote_filepath, local_filepath):
        return self._internal_resource.sftp_get(
            remote_filepath=remote_filepath, local_filepath=local_filepath
        )

    def sftp_put(self, remote_filepath, local_filepath, confirm=True):
        return self._internal_resource.sftp_put(
            remote_filepath=remote_filepath,
            local_filepath=local_filepath,
            confirm=confirm,
        )
