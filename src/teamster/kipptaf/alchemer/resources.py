from alchemer import AlchemerSession
from dagster import ConfigurableResource, InitResourceContext
from pydantic import PrivateAttr


class AlchemerResource(ConfigurableResource):
    api_token: str
    api_token_secret: str
    api_version: str
    timeout: int

    _client: AlchemerSession = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._client = AlchemerSession(
            api_token=self.api_token,
            api_token_secret=self.api_token_secret,
            api_version=self.api_version,
            timeout=self.timeout,
            time_zone="America/New_York",  # pre-determined by Alchemer
        )
