from dagster import StringSource, resource
from powerschool import PowerSchool


@resource(
    config_schema={
        "host": StringSource,
        "client_id": StringSource,
        "client_secret": StringSource,
    }
)
def powerschool(init_context):
    credentials = (
        init_context.resource_config["client_id"],
        init_context.resource_config["client_secret"],
    )
    client = PowerSchool(
        host=init_context.resource_config["host"],
        auth=credentials,
    )
    return client
