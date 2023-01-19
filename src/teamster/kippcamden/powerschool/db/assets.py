from dagster import config_from_files

from teamster.core.powerschool.db.assets import table_asset_factory

from ... import CODE_LOCATION

ps_db_assets = [
    table_asset_factory(**cfg, code_location=CODE_LOCATION)
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets.yaml"]
    )["assets"]
]

ps_db_partitioned_assets = [
    table_asset_factory(**cfg, code_location=CODE_LOCATION)
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-partitioned.yaml"]
    )["assets"]
]

__all__ = ps_db_assets + ps_db_partitioned_assets
