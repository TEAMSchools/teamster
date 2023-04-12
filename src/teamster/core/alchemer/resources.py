from alchemer import AlchemerSession
from dagster import InitResourceContext, StringSource, resource

from teamster.core.utils.variables import LOCAL_TIME_ZONE


@resource(
    config_schema={
        "api_token": StringSource,
        "api_token_secret": StringSource,
        "api_version": StringSource,
    }
)
def alchemer_resource(context: InitResourceContext):
    return AlchemerSession(
        api_token=context.resource_config["api_token"],
        api_token_secret=context.resource_config["api_token_secret"],
        api_version=context.resource_config["api_version"],
        time_zone=LOCAL_TIME_ZONE,
    )
