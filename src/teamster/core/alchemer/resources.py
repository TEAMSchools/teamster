from alchemer import AlchemerSession
from dagster import ConfigurableResource, InitResourceContext
from pydantic import PrivateAttr


class AlchemerResource(ConfigurableResource):
    api_token: str
    api_token_secret: str
    api_version: str

    _client: AlchemerSession = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._client = AlchemerSession(
            api_token=self.api_token,
            api_token_secret=self.api_token_secret,
            api_version=self.api_version,
            time_zone="US/Eastern",  # determined by Alchemer
        )
