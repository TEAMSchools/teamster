from alchemer import AlchemerSession
from dagster import ConfigurableResource, InitResourceContext, StringSource, resource
from pydantic import PrivateAttr


class AlchemerResource(ConfigurableResource):
    api_token: str
    api_token_secret: str
    api_version: str

    _client: AlchemerSession = PrivateAttr()

    def setup_for_execution(self, context):
        self._client = AlchemerSession(
            api_token=self.api_token,
            api_token_secret=self.api_token_secret,
            api_version=self.api_version,
            time_zone="US/Eastern",  # determined by Alchemer
        )


@resource(
    config_schema={
        "api_token": StringSource,
        "api_token_secret": StringSource,
        "api_version": StringSource,
        "timezone": StringSource,
    }
)
def alchemer_resource(context: InitResourceContext):
    return AlchemerSession(
        api_token=context.resource_config["api_token"],
        api_token_secret=context.resource_config["api_token_secret"],
        api_version=context.resource_config["api_version"],
        time_zone=context.resource_config["timezone"],
    )
