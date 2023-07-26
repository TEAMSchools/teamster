from itertools import chain
from typing import Mapping, Optional, Sequence, Set

from dagster import AssetKey, AssetOut, Config, OpExecutionContext, Output, op
from dagster_airbyte import AirbyteOutput
from dagster_airbyte.utils import generate_materializations


class AirbyteMaterializationOpConfig(Config):
    airbyte_outputs: list[dict]


def build_airbyte_materialization_op(
    connection_id: str,
    destination_tables: Sequence[str],
    asset_key_prefix: Optional[Sequence[str]] = None,
    normalization_tables: Optional[Mapping[str, Set[str]]] = None,
):
    tables = chain.from_iterable(
        chain(
            [destination_tables],
            normalization_tables.values() if normalization_tables else [],
        )
    )

    outputs = {
        table: AssetOut(key=AssetKey([*asset_key_prefix, table])) for table in tables
    }

    @op(name="airbyte_materialization_op", outs=outputs)
    def _op(context: OpExecutionContext, config: AirbyteMaterializationOpConfig):
        for output in config.airbyte_outputs:
            namespace_format = output["connection_details"]["namespaceFormat"].split(
                "_"
            )

            for materialization in generate_materializations(
                output=AirbyteOutput(**output),
                asset_key_prefix=[namespace_format[0], "_".join(namespace_format[1:])],
            ):
                yield Output(
                    value=None,
                    output_name=materialization.asset_key.path[-1],
                    metadata=materialization.metadata,
                )

    return _op
