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
