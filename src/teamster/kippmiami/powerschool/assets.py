from dagster import DynamicPartitionsDefinition, config_from_files

from teamster.core.powerschool.assets import build_powerschool_table_asset

from .. import CODE_LOCATION

config_dir = f"src/teamster/{CODE_LOCATION}/config/assets/powerschool"

dynamic_partitions_def = DynamicPartitionsDefinition(
    name=f"{CODE_LOCATION}_powerschool_dynamic_partitions"
)

nonpartition_assets = [
    build_powerschool_table_asset(**cfg, code_location=CODE_LOCATION)
    for cfg in config_from_files([(f"{config_dir}/assets-nonpartition.yaml")])["assets"]
]

partition_assets = []
for suffix in ["transactiondate", "whenmodified"]:
    config = config_from_files([f"{config_dir}/assets-{suffix}.yaml"])

    partition_column = config["partition_column"]
    for asset in config["assets"]:
        partition_assets.append(
            build_powerschool_table_asset(
                **asset,
                code_location=CODE_LOCATION,
                partitions_def=dynamic_partitions_def,
                metadata={"partition_column": partition_column},
            )
        )

__all__ = [
    *partition_assets,
    *nonpartition_assets,
]
