from dagster import ConfigurableResource, InitResourceContext
from ldap3 import ALL, NTLM, Connection, Server
from pydantic import Field, PrivateAttr


class LdapResource(ConfigurableResource):
    host: str
    port: str
    user: str
    password: str = Field(repr=False)

    _server: Server = PrivateAttr()
    _connection: Connection = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._server = Server(
            host=self.host, port=int(self.port), use_ssl=True, get_info=ALL
        )
        self._connection = Connection(
            server=self._server,
            user=self.user,
            password=self.password,
            authentication=NTLM,
        )

        self._connection.bind()
