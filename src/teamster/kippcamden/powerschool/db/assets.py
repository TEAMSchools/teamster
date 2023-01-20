from dagster import config_from_files

from teamster.core.powerschool.db.assets import table_asset_factory
from teamster.kippcamden import CODE_LOCATION, POWERSCHOOL_PARTITION_START_DATE

ps_daily_assets = [
    table_asset_factory(**cfg, code_location=CODE_LOCATION)
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-daily.yaml"]
    )["assets"]
]

ps_hourly_assets = [
    table_asset_factory(
        **cfg,
        code_location=CODE_LOCATION,
        partition_start_date=POWERSCHOOL_PARTITION_START_DATE,
    )
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-hourly.yaml"]
    )["assets"]
]

ps_assignment_assets = [
    table_asset_factory(
        **cfg,
        code_location=CODE_LOCATION,
        where_column="whenmodified",
        partition_start_date=POWERSCHOOL_PARTITION_START_DATE,
    )
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-assignment.yaml"]
    )["assets"]
]

ps_contacts_assets = [
    table_asset_factory(
        **cfg,
        code_location=CODE_LOCATION,
        where_column="whenmodified",
        partition_start_date=POWERSCHOOL_PARTITION_START_DATE,
    )
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-contacts.yaml"]
    )["assets"]
]

ps_custom_assets = [
    table_asset_factory(
        **cfg,
        code_location=CODE_LOCATION,
        where_column="whenmodified",
        partition_start_date=POWERSCHOOL_PARTITION_START_DATE,
    )
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-custom.yaml"]
    )["assets"]
]
