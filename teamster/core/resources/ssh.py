from dagster import BoolSource, Field, IntSource, Noneable, Shape, StringSource
from dagster import _check as check
from dagster import resource
from dagster._utils import merge_dicts
from dagster_ssh import SSHResource
from paramiko.config import SSH_PORT
from sshtunnel import SSHTunnelForwarder


class SSHResource(SSHResource):
    def __init__(
        self,
        remote_host,
        remote_port,
        username=None,
        password=None,
        key_file=None,
        key_string=None,
        timeout=10,
        keepalive_interval=30,
        compress=True,
        no_host_key_check=True,
        allow_host_key_change=False,
        logger=None,
        tunnel=None,
    ):
        self.tunnel = check.opt_dict_param(tunnel, "tunnel")

        super().__init__(
            remote_host,
            remote_port,
            username,
            password,
            key_file,
            key_string,
            timeout,
            keepalive_interval,
            compress,
            no_host_key_check,
            allow_host_key_change,
            logger,
        )

    def get_tunnel(self):
        if self.tunnel["local_bind_port"] is not None:
            local_bind_address = ("localhost", self.tunnel["local_bind_port"])
        else:
            local_bind_address = ("localhost",)

        # Will prefer key string if specified, otherwise use the key file
        pkey = self.key_obj if self.key_obj else self.key_file

        if self.password and self.password.strip():
            client = SSHTunnelForwarder(
                self.remote_host,
                ssh_port=self.remote_port,
                ssh_username=self.username,
                ssh_password=self.password,
                ssh_pkey=pkey,
                ssh_proxy=self.host_proxy,
                local_bind_address=local_bind_address,
                remote_bind_address=(
                    self.tunnel["remote_bind_host"],
                    self.tunnel["remote_bind_port"],
                ),
                logger=self.log,
            )
        else:
            client = SSHTunnelForwarder(
                self.remote_host,
                ssh_port=self.remote_port,
                ssh_username=self.username,
                ssh_pkey=pkey,
                ssh_proxy=self.host_proxy,
                local_bind_address=local_bind_address,
                remote_bind_address=(
                    self.tunnel["remote_bind_host"],
                    self.tunnel["remote_bind_port"],
                ),
                host_pkey_directories=[],
                logger=self.log,
            )

        return client


SSH_RESOURCE_CONFIG = {
    "remote_host": Field(
        StringSource, description="remote host to connect to", is_required=True
    ),
    "remote_port": Field(
        IntSource,
        description="port of remote host to connect (Default is paramiko SSH_PORT)",
        is_required=False,
        default_value=SSH_PORT,
    ),
    "tunnel": Field(
        Shape(
            {
                "remote_bind_host": Field(
                    StringSource,
                    description="remote host to bind to when tunneling",
                    is_required=False,
                    default_value="localhost",
                ),
                "remote_bind_port": Field(
                    IntSource,
                    description="port of remote host to bind to when tunneling",
                    is_required=True,
                ),
                "local_bind_port": Field(
                    Noneable(IntSource),
                    description="port of local host to bind to when tunneling",
                    is_required=False,
                    default_value=None,
                ),
            }
        ),
        is_required=False,
    ),
    "username": Field(
        StringSource,
        description="username to connect to the remote_host",
        is_required=False,
    ),
    "password": Field(
        StringSource,
        description="password of the username to connect to the remote_host",
        is_required=False,
    ),
    "key_file": Field(
        StringSource,
        description="key file to use to connect to the remote_host.",
        is_required=False,
    ),
    "key_string": Field(
        StringSource,
        description="key string to use to connect to remote_host",
        is_required=False,
    ),
    "timeout": Field(
        IntSource,
        description="timeout for the attempt to connect to the remote_host.",
        is_required=False,
        default_value=10,
    ),
    "keepalive_interval": Field(
        IntSource,
        description="send a keepalive packet to remote host every keepalive_interval seconds",
        is_required=False,
        default_value=30,
    ),
    "compress": Field(BoolSource, is_required=False, default_value=True),
    "no_host_key_check": Field(BoolSource, is_required=False, default_value=True),
    "allow_host_key_change": Field(BoolSource, is_required=False, default_value=False),
}


@resource(config_schema=SSH_RESOURCE_CONFIG)
def ssh_resource(init_context):
    args = init_context.resource_config
    args = merge_dicts(init_context.resource_config, {"logger": init_context.log})
    return SSHResource(**args)
