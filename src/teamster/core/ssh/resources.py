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
