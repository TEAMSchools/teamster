from urllib.parse import quote

from dagster import ConfigurableResource


class OracleResource(ConfigurableResource):
    """Connection config for the PowerSchool Oracle database (dlt path).

    The DB host is the tunnel-local endpoint (normally localhost) because the
    SSH tunnel forwards localhost:1521 to the PowerSchool server.
    """

    user: str
    password: str
    host: str
    port: str
    service_name: str

    def connection_url(self) -> str:
        password = quote(self.password, safe="")

        return (
            f"oracle+oracledb://{self.user}:{password}@{self.host}:{self.port}"
            f"/?service_name={self.service_name}"
        )
