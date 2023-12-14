import pathlib
from typing import Iterator, Optional, Sequence

import yaml
from dagster import (
    Any,
    AssetKey,
    AssetMaterialization,
    AssetOut,
    AssetsDefinition,
    Nothing,
    OpExecutionContext,
    Output,
)
from dagster import _check as check
from dagster import multi_asset

from .. import CODE_LOCATION


def generate_materializations(
    asset_keys: list[AssetKey],
) -> Iterator[AssetMaterialization]:
    for asset_key in asset_keys:
        yield AssetMaterialization(
            asset_key=asset_key, description="Table generated via Fivetran sync"
        )


def build_fivetran_assets(
    connector_id: str,
    destination_tables: Sequence[str],
    asset_key_prefix: Sequence[str] = [],
    group_name: Optional[str] = None,
) -> Sequence[AssetsDefinition]:
    asset_key_prefix = check.opt_sequence_param(
        asset_key_prefix, "asset_key_prefix", of_type=str
    )

    tracked_asset_keys = {
        table: AssetKey([*asset_key_prefix, *table.split(".")])
        for table in destination_tables
    }

    @multi_asset(
        name=f"fivetran_sync_{connector_id}",
        outs={
            "_".join(key.path): AssetOut(
                key=tracked_asset_keys[table], dagster_type=Nothing, is_required=False
            )
            for table, key in tracked_asset_keys.items()
        },
        compute_kind="fivetran",
        group_name=group_name,
        can_subset=True,
    )
    def _assets(context: OpExecutionContext) -> Any:
        for materialization in generate_materializations(
            list(context.selected_asset_keys)
        ):
            # scan through all tables actually created,
            # if it was expected then emit an Output.
            # otherwise, emit a runtime AssetMaterialization
            if materialization.asset_key in tracked_asset_keys.values():
                yield Output(
                    value=None,
                    output_name="_".join(materialization.asset_key.path),
                    metadata=materialization.metadata,
                )
            else:
                yield materialization

    return [_assets]


_all: list[AssetsDefinition] = []

config_path = pathlib.Path(__file__).parent / "config"

for config_file in config_path.glob("*.yaml"):
    config = yaml.safe_load(config_file.read_text())

    connector_name = config["connector_name"]

    destination_tables = []
    for schema in config["schemas"]:
        schema_name = schema.get("name")

        if schema_name is not None:
            destination_table_schema_name = f"{connector_name}.{schema_name}"
        else:
            destination_table_schema_name = connector_name

        for table in schema["destination_tables"]:
            destination_tables.append(f"{destination_table_schema_name}.{table}")

    _all.extend(
        build_fivetran_assets(
            connector_id=config["connector_id"],
            destination_tables=destination_tables,
            asset_key_prefix=[CODE_LOCATION],
            group_name=config.get("group_name", connector_name),
        )
    )
