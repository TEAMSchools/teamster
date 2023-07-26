from dagster import Config, OpExecutionContext, op
from dagster_airbyte import AirbyteOutput
from dagster_airbyte.utils import generate_materializations


class AirbyteMaterializationOpConfig(Config):
    airbyte_outputs: list[dict]


@op
def airbyte_materialization_op(
    context: OpExecutionContext, config: AirbyteMaterializationOpConfig
):
    for output in config.airbyte_outputs:
        airbyte_output = AirbyteOutput(**output)
        namespace_format = output["connection_details"]["namespaceFormat"].split("_")

        asset_key_prefix = [namespace_format[0], "_".join(namespace_format[1:])]

        context.log.debug(airbyte_output)
        context.log.debug(asset_key_prefix)

        yield from generate_materializations(
            output=airbyte_output, asset_key_prefix=asset_key_prefix
        )


__all__ = [
    airbyte_materialization_op,
]
