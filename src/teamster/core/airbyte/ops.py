from dagster import Config, OpExecutionContext, op
from dagster_airbyte.utils import generate_materializations


class AirbyteMaterializationOpConfig(Config):
    airbyte_outputs: list


@op
def airbyte_materialization_op(
    context: OpExecutionContext, config: AirbyteMaterializationOpConfig
):
    for output in config.airbyte_outputs:
        namespace_format = output.connection_details["namespaceFormat"].split("_")

        yield from generate_materializations(
            output=output,
            asset_key_prefix=[namespace_format[0], "_".join(namespace_format[1:])],
        )


__all__ = [
    airbyte_materialization_op,
]
