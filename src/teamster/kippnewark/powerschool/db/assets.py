from dagster import config_from_files

from teamster.core.powerschool.db.assets import table_asset_factory

from ... import CODE_LOCATION

ps_db_assets = [
    table_asset_factory(**cfg)
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets.yaml"]
    )["assets"]
]
