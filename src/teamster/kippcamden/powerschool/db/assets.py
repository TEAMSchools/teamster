from dagster import config_from_files

from teamster.core.powerschool.db.assets import table_asset_factory
from teamster.kippcamden import CODE_LOCATION, POWERSCHOOL_PARTITION_START_DATE

ps_db_assets = [
    table_asset_factory(**cfg, code_location=CODE_LOCATION)
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets.yaml"]
    )["assets"]
]

ps_db_partitioned_assets = [
    table_asset_factory(
        **cfg,
        code_location=CODE_LOCATION,
        partition_start_date=POWERSCHOOL_PARTITION_START_DATE,
    )
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-partitioned.yaml"]
    )["assets"]
]
