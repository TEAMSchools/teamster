from dagster import AssetsDefinition, Config, OpExecutionContext, Out, Output, op
from dagster_airbyte import AirbyteOutput
from dagster_airbyte.utils import generate_materializations


class AirbyteMaterializationOpConfig(Config):
    airbyte_outputs: list[dict]


def build_airbyte_materialization_op(asset_defs: list[AssetsDefinition]):
    outputs = {
        asset_key.path[-1]: Out(is_required=False)
        for asset_def in asset_defs
        for asset_key in asset_def.keys
    }

    @op(name="airbyte_materialization_op", out=outputs)
    def _op(context: OpExecutionContext, config: AirbyteMaterializationOpConfig):
        for output in config.airbyte_outputs:
            namespace = output["connection_details"]["namespaceFormat"].split("_")

            for materialization in generate_materializations(
                output=AirbyteOutput(**output),
                asset_key_prefix=[namespace[0], "_".join(namespace[1:])],
            ):
                yield Output(
                    value=True,
                    output_name=materialization.asset_key.path[-1],
                    metadata=materialization.metadata,
                )

    return _op
