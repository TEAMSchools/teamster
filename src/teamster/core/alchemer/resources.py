from alchemer import AlchemerSession
from dagster import InitResourceContext, StringSource, resource


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
